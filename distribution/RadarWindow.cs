using System;
using System.IO;
using System.Drawing;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

// Only the local Radar interface is embedded. Auction sites open externally.
internal sealed class RadarWindow : Form {
    readonly Uri root;
    readonly string token, dataDirectory;
    readonly Action hidden;
    readonly ContextMenuStrip options;
    readonly Panel body = new Panel { Dock=DockStyle.Fill };
    readonly ToolStripStatusLabel status = new ToolStripStatusLabel { Spring=true, TextAlign=ContentAlignment.MiddleLeft, Text="Iniciando o Radar…" };
    WebView2 view;
    bool initializing, exiting;

    public RadarWindow(string url,string sessionToken,string data,Icon icon,Action onHidden,ContextMenuStrip menu) {
        root=new Uri(url);token=sessionToken;dataDirectory=data;hidden=onHidden;options=menu;
        Text="Radar de Leilões";Icon=icon;StartPosition=FormStartPosition.CenterScreen;
        AutoScaleMode=AutoScaleMode.Dpi;MinimumSize=new Size(820,600);ClientSize=new Size(1180,780);
        BackColor=Color.FromArgb(245,247,251);Font=new Font("Segoe UI",10);
        var strip=new StatusStrip { SizingGrip=true,BackColor=Color.White,Padding=new Padding(12,4,12,4) };
        var hide=new ToolStripButton("Manter em segundo plano");hide.Click+=(s,e)=>Close();
        var more=new ToolStripDropDownButton("Opções");more.DropDown=options;
        strip.Items.AddRange(new ToolStripItem[]{status,hide,more});Controls.Add(body);Controls.Add(strip);
        FormClosing+=(s,e)=>{
            if(!exiting && e.CloseReason==CloseReason.UserClosing){e.Cancel=true;Hide();hidden();}
        };
        Shown+=async(s,e)=>await Initialize();
    }
    public void SetStatus(string text){status.Text=text;status.ToolTipText=text;}
    public void ShowRadar(){Show();if(WindowState==FormWindowState.Minimized)WindowState=FormWindowState.Normal;BringToFront();Activate();}
    public void Shutdown(){exiting=true;Dispose();}
    bool LocalPage(string address) {
        Uri uri;return Uri.TryCreate(address,UriKind.Absolute,out uri) && uri.Scheme==root.Scheme && uri.Authority==root.Authority && String.IsNullOrEmpty(uri.UserInfo) && uri.AbsolutePath=="/";
    }
    void External(string address) {
        Uri uri;
        if(!Uri.TryCreate(address,UriKind.Absolute,out uri) || (uri.Scheme!="https" && uri.Scheme!="http") || !String.IsNullOrEmpty(uri.UserInfo) || uri.IsLoopback)return;
        try{Process.Start(new ProcessStartInfo(uri.AbsoluteUri){UseShellExecute=true});}
        catch{MessageBox.Show(this,"Não foi possível abrir o link. Confira se há um navegador instalado.","Radar de Leilões");}
    }
    void Failure(string message) {
        if(IsDisposed)return;
        body.Controls.Clear();
        var panel=new FlowLayoutPanel { Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,Padding=new Padding(40),WrapContents=false };
        panel.Controls.Add(new Label { Text="Vamos abrir o Radar",AutoSize=true,Font=new Font("Segoe UI",20,FontStyle.Bold) });
        panel.Controls.Add(new Label { Text=message,Width=650,Height=110,Margin=new Padding(3,20,3,20) });
        var retry=new Button { Text="Tentar novamente",Width=180,Height=40 };retry.Click+=async(s,e)=>await Initialize();panel.Controls.Add(retry);
        body.Controls.Add(panel);
    }
    async Task Initialize() {
        if(initializing||IsDisposed)return;
        initializing=true;
        if(view!=null){view.Dispose();view=null;}
        body.Controls.Clear();
        var loading=new Label { Text="Abrindo o Radar…",Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleCenter,Font=new Font("Segoe UI",18) };body.Controls.Add(loading);
        try {
            var environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(dataDirectory,"janela-webview"));
            if(IsDisposed)return;
            view=new WebView2 { Dock=DockStyle.Fill,DefaultBackgroundColor=BackColor,AccessibleName="Radar de Leilões" };
            body.Controls.Add(view);view.BringToFront();
            await view.EnsureCoreWebView2Async(environment);
            if(IsDisposed)return;
            body.Controls.Remove(loading);loading.Dispose();
            var core=view.CoreWebView2;
            core.Settings.AreHostObjectsAllowed=false;core.Settings.IsWebMessageEnabled=false;
            core.Settings.AreDevToolsEnabled=false;core.Settings.AreDefaultContextMenusEnabled=false;
            core.Settings.IsStatusBarEnabled=false;core.Settings.IsGeneralAutofillEnabled=false;core.Settings.IsPasswordAutosaveEnabled=false;
            core.Settings.AreDefaultScriptDialogsEnabled=false;
            core.ScriptDialogOpening+=(s,e)=>{
                var deferral=e.GetDeferral();
                BeginInvoke(new Action(()=>{
                    try {
                        if(e.Kind==CoreWebView2ScriptDialogKind.Alert){MessageBox.Show(this,e.Message,"Radar de Leilões",MessageBoxButtons.OK,MessageBoxIcon.Information);e.Accept();}
                        else if(e.Kind==CoreWebView2ScriptDialogKind.Confirm && MessageBox.Show(this,e.Message,"Radar de Leilões",MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes)e.Accept();
                    }finally{deferral.Complete();}
                }));
            };
            core.PermissionRequested+=(s,e)=>e.State=CoreWebView2PermissionState.Deny;
            core.NavigationStarting+=(s,e)=>{if(!LocalPage(e.Uri)){e.Cancel=true;if(e.IsUserInitiated)External(e.Uri);}};
            core.NewWindowRequested+=(s,e)=>{e.Handled=true;if(e.IsUserInitiated)External(e.Uri);};
            core.DownloadStarting+=(s,e)=>{
                // The only downloadable artifact is the workbook fetched from our server.
                if(!e.DownloadOperation.Uri.StartsWith("blob:"+root.AbsoluteUri,StringComparison.Ordinal)) {e.Cancel=true;return;}
                e.Handled=true;
                var deferral=e.GetDeferral();
                BeginInvoke(new Action(()=>{
                    try {
                        using(var dialog=new SaveFileDialog { Title="Salvar cópia da planilha",Filter="Planilha Excel (*.xlsx)|*.xlsx",FileName="Radar-de-Leiloes.xlsx",DefaultExt="xlsx",AddExtension=true,OverwritePrompt=true }) {
                            if(dialog.ShowDialog(this)==DialogResult.OK)e.ResultFilePath=dialog.FileName;else e.Cancel=true;
                        }
                    } finally{deferral.Complete();}
                }));
            };
            core.NavigationCompleted+=(s,e)=>{
                if(!e.IsSuccess)Failure("Não foi possível carregar a tela. Aguarde alguns segundos e tente novamente. Seus dados continuam salvos.");
            };
            core.ProcessFailed+=(s,e)=>{if(!IsDisposed)BeginInvoke(new Action(()=>Failure("A janela encontrou um problema. Clique em Tentar novamente para recuperar a tela. As buscas continuam em segundo plano.")));};
            core.Navigate(root.AbsoluteUri+"#"+token);
        } catch(WebView2RuntimeNotFoundException) {
            Failure("Falta um componente da Microsoft para abrir esta janela. Conecte-se à internet e execute o instalador do Radar novamente. Ele instalará o WebView2. Seus dados serão mantidos.");
        } catch(Exception e) {
            try{File.AppendAllText(Path.Combine(dataDirectory,"data","janela-erros.log"),DateTime.Now+" "+e.GetType().Name+Environment.NewLine);}catch{}
            Failure("Não foi possível abrir a janela. Tente novamente. Se o problema continuar, encerre o Radar pelo menu Opções e execute o instalador novamente. Seus dados serão mantidos.");
        } finally{initializing=false;}
    }
}

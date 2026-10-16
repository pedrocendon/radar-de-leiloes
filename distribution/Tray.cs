using System;
using System.IO;
using System.Net;
using System.Text;
using System.Drawing;
using System.Diagnostics;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Runtime.InteropServices;
using System.Threading;
using System.Security.Cryptography;

internal sealed class RadarTray : ApplicationContext {
    readonly NotifyIcon tray = new NotifyIcon();
    readonly ContextMenuStrip menu = new ContextMenuStrip();
    readonly ToolStripMenuItem status = new ToolStripMenuItem("Iniciando o Radar…");
    readonly ToolStripMenuItem next = new ToolStripMenuItem("Consultando a próxima busca…");
    readonly ToolStripMenuItem open = new ToolStripMenuItem("Abrir Radar de Leilões");
    readonly ToolStripMenuItem activity = new ToolStripMenuItem("Ver situação do Radar");
    readonly ToolStripMenuItem search = new ToolStripMenuItem("Buscar novidades agora");
    readonly ToolStripMenuItem schedule = new ToolStripMenuItem("Ativar buscas automáticas");
    readonly ToolStripMenuItem exit = new ToolStripMenuItem("Encerrar o Radar");
    readonly ToolStripMenuItem updates = new ToolStripMenuItem("Verificar nova versão do Radar");
    string notifiedVersion;
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    readonly Dictionary<string,Icon> icons = new Dictionary<string,Icon>();
    readonly string sessionFile, token, rootUrl;
    readonly Process owner;
    readonly Icon appIcon;
    Form activityWindow;
    RadarWindow radarWindow;
    readonly EventWaitHandle showSignal;
    bool pendingShow;
    Label activityStatus, activityNext;
    bool refreshing, changing, enabled, disposed, connected;
    int hours=24;
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr handle);

    static string SignalName(string session) {
        using(var hash=SHA256.Create())return "Local\\RadarLeiloes.Show."+BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Path.GetFullPath(session).ToUpperInvariant()))).Replace("-","");
    }
    public RadarTray(string session, int pid, bool show) {
        sessionFile=session; owner=Process.GetProcessById(pid);
        showSignal=new EventWaitHandle(false,EventResetMode.AutoReset,SignalName(session));pendingShow=show;
        var settings=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(session,Encoding.UTF8));
        var uri=new Uri(Convert.ToString(settings["url"]));
        if(uri.Scheme!="http" || uri.Host!="127.0.0.1" || !String.IsNullOrEmpty(uri.UserInfo) || uri.AbsolutePath!="/") throw new InvalidDataException("Sessão local inválida.");
        rootUrl=uri.AbsoluteUri; token=Convert.ToString(settings["token"]);
        appIcon=new Icon(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"radar.ico"));
        icons.Add("idle",Badge(Color.Gray)); icons.Add("scheduled",Badge(Color.SeaGreen));
        icons.Add("busy",Badge(Color.DodgerBlue)); icons.Add("error",Badge(Color.DarkOrange));
        status.Enabled=false; next.Enabled=false;search.Enabled=false;schedule.Enabled=false;exit.Enabled=false;
        menu.Items.AddRange(new ToolStripItem[]{status,next,new ToolStripSeparator(),open,activity,search,schedule,updates,new ToolStripSeparator(),exit});
        updates.Click+=async(s,e)=>{OpenRadar();await Change("update_check",new Dictionary<string,object>());};
        tray.BalloonTipClicked+=(s,e)=>OpenRadar();
        activity.Click+=(s,e)=>ShowActivity();
        open.Click+=(s,e)=>OpenRadar(); tray.DoubleClick+=(s,e)=>OpenRadar();
        search.Click+=async(s,e)=>await Change("search",new Dictionary<string,object>());
        schedule.Click+=async(s,e)=>await Change("schedule",new Dictionary<string,object>{{"enabled",!enabled},{"hours",hours}});
        exit.Click+=async(s,e)=>await Change("close",new Dictionary<string,object>());
        tray.ContextMenuStrip=menu;tray.Icon=icons["idle"];tray.Text="Radar de Leilões — iniciando";tray.Visible=true;
        timer.Interval=2000;timer.Tick+=async(s,e)=>await Refresh();timer.Start();
        // The message loop runs on this STA thread; network calls run in the pool.
        menu.Opening+=async(s,e)=>await Refresh();
        if(Environment.GetEnvironmentVariable("RADAR_SHOW_STATUS")=="1")ShowActivity();
    }
    void ShowActivity() {
        if(activityWindow==null) {
            activityWindow=new Form { Text="Radar de Leilões — segundo plano",ClientSize=new Size(450,245),StartPosition=FormStartPosition.CenterScreen,FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,Icon=appIcon,BackColor=Color.White,Font=new Font("Segoe UI",10) };
            var title=new Label { Text="Radar em segundo plano",Location=new Point(24,20),Size=new Size(402,32),Font=new Font("Segoe UI",15,FontStyle.Bold),ForeColor=Color.FromArgb(32,62,96) };
            activityStatus=new Label { Location=new Point(24,65),Size=new Size(402,28) };
            activityNext=new Label { Location=new Point(24,98),Size=new Size(402,38) };
            var button=new Button { Text="Abrir programa",Location=new Point(24,144),Size=new Size(165,35) };button.Click+=(s,e)=>OpenRadar();
            var options=new Button { Text="Opções",Location=new Point(205,144),Size=new Size(120,35) };options.Click+=(s,e)=>menu.Show(options,new Point(0,options.Height));
            var hint=new Label { Text="Você pode fechar esta janela. O Radar continua aberto no ícone perto do relógio. Use Encerrar o Radar para sair.",Location=new Point(24,191),Size=new Size(402,47),ForeColor=Color.DimGray,Font=new Font("Segoe UI",9) };
            activityWindow.Controls.AddRange(new Control[]{title,activityStatus,activityNext,button,options,hint});
            activityWindow.FormClosing+=(s,e)=>{if(!disposed){e.Cancel=true;activityWindow.Hide();}};
        }
        UpdateActivity();activityWindow.Show();activityWindow.WindowState=FormWindowState.Normal;activityWindow.Activate();
    }
    void UpdateActivity(){if(activityWindow!=null){activityStatus.Text=status.Text;activityNext.Text=next.Text;}if(radarWindow!=null)radarWindow.SetStatus(status.Text+" • "+next.Text);}
    Icon Badge(Color color) {
        using(var bitmap=appIcon.ToBitmap()) {
            using(var g=Graphics.FromImage(bitmap)) {
                int d=Math.Max(10,bitmap.Width/2), x=bitmap.Width-d;
                using(var brush=new SolidBrush(color))g.FillEllipse(brush,x,x,d,d);
                using(var pen=new Pen(Color.White,Math.Max(1,bitmap.Width/32)))g.DrawEllipse(pen,x,x,d-1,d-1);
            }
            IntPtr handle=bitmap.GetHicon();try{return (Icon)Icon.FromHandle(handle).Clone();}finally{DestroyIcon(handle);}
        }
    }
    Dictionary<string,object> Request(string action,Dictionary<string,object> payload=null) {
        var request=(HttpWebRequest)WebRequest.Create(rootUrl+"api/"+action);
        request.Proxy=null;request.AllowAutoRedirect=false;request.Timeout=1500;request.ReadWriteTimeout=1500;
        request.Headers["X-Radar-Token"]=token;
        if(payload!=null) {
            request.Method="POST";request.ContentType="application/json";
            var bytes=Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(payload));
            request.ContentLength=bytes.Length;using(var stream=request.GetRequestStream())stream.Write(bytes,0,bytes.Length);
        }
        try {
            using(var response=request.GetResponse())using(var reader=new StreamReader(response.GetResponseStream()))
                return new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(reader.ReadToEnd());
        } catch(WebException error) {
            if(error.Response!=null)using(var response=error.Response)using(var reader=new StreamReader(response.GetResponseStream())) {
                var result=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(reader.ReadToEnd());
                if(result.ContainsKey("error"))throw new InvalidOperationException(Convert.ToString(result["error"]));
            }
            throw new InvalidOperationException("Não foi possível falar com o Radar. Aguarde alguns segundos.");
        }
    }
    void OpenRadar() {
        if(radarWindow==null)radarWindow=new RadarWindow(rootUrl,token,Path.GetDirectoryName(Path.GetDirectoryName(sessionFile)),appIcon,NotifyHidden,menu);
        radarWindow.ShowRadar();UpdateActivity();
    }
    void NotifyHidden() {
        string marker=Path.Combine(Path.GetDirectoryName(sessionFile),"aviso-segundo-plano-visto.txt");
        if(File.Exists(marker))return;
        tray.ShowBalloonTip(7000,"O Radar continua aberto", "As buscas automáticas continuam se a agenda estiver ativada. Abra pelo atalho ou pelo ícone perto do relógio. Use Encerrar o Radar para sair.",ToolTipIcon.Info);
        try{File.WriteAllText(marker,"1");}catch{}
    }
    async Task Change(string action,Dictionary<string,object> payload) {
        if(changing||!connected)return;
        changing=true;search.Enabled=schedule.Enabled=exit.Enabled=false;
        try {
            await Task.Run(()=>Request(action,payload));
            if(action=="close"){ExitThread();return;}
        } catch(Exception e) {
            if(!disposed)tray.ShowBalloonTip(5000,"Radar de Leilões",e.Message,ToolTipIcon.Warning);
        } finally {changing=false;}
        await Refresh();
    }
    async Task Refresh() {
        if(disposed)return;
        if(owner.HasExited || !File.Exists(sessionFile)){ExitThread();return;}
        if(showSignal.WaitOne(0)||pendingShow){pendingShow=false;OpenRadar();}
        if(refreshing||changing)return;
        refreshing=true;
        try {
            var state=await Task.Run(()=>Request("background"));
            if(disposed)return;
            var job=(Dictionary<string,object>)state["job"];
            var plan=(Dictionary<string,object>)state["schedule"];
            bool busy=Convert.ToBoolean(job["busy"]),failed=Convert.ToBoolean(job["error"]);
            enabled=Convert.ToBoolean(plan["enabled"]);hours=Convert.ToInt32(plan["hours"]);connected=true;
            string label=busy?(Convert.ToString(job["kind"])=="search"?"Buscando imóveis…":"Atualizando a planilha…"):failed?"Última atualização com erro":enabled?"Buscas automáticas ativadas":"Aberto • buscas automáticas desativadas";
            if(busy && Convert.ToString(job["kind"])=="software")label="Atualizando o programa…";
            if(state.ContainsKey("updates")) {
                var update=(Dictionary<string,object>)state["updates"];
                string available=Convert.ToString(update.ContainsKey("latest_version")?update["latest_version"]:null);
                if(Convert.ToString(update["status"])=="available" && available!=notifiedVersion) {
                    notifiedVersion=available;
                    tray.ShowBalloonTip(9000,"Nova versão do Radar", "A versão "+available+" está disponível. Abra o Radar e escolha Atualizações para instalar.",ToolTipIcon.Info);
                }
            }
            status.Text=label;
            next.Text=busy?"Aguarde a conclusão da atualização":enabled&&plan["next_run"]!=null?"Próxima busca: "+new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc).AddSeconds(Convert.ToDouble(plan["next_run"])).ToLocalTime().ToString("dd/MM HH:mm"):"Use Buscar novidades agora para consultar";
            tray.Icon=icons[busy?"busy":failed?"error":enabled?"scheduled":"idle"];
            string tip=busy?"Radar — "+label:enabled?"Radar — "+next.Text:failed?"Radar — última atualização com erro":"Radar aberto — buscas automáticas desativadas";
            tray.Text=tip.Length>63?tip.Substring(0,63):tip;
            schedule.Text=enabled?"Pausar buscas automáticas":"Ativar buscas automáticas ("+hours+" h)";
            open.Enabled=true;search.Enabled=schedule.Enabled=exit.Enabled=updates.Enabled=!busy;
            UpdateActivity();
        } catch {
            if(disposed)return;
            connected=false;tray.Icon=icons["error"];tray.Text="Radar — conexão indisponível";
            status.Text="Não foi possível confirmar o estado do Radar";next.Text="Tentando reconectar…";
            open.Enabled=search.Enabled=schedule.Enabled=exit.Enabled=false;
            UpdateActivity();
        } finally {refreshing=false;}
    }
    protected override void ExitThreadCore() {
        if(!disposed){disposed=true;timer.Stop();tray.Visible=false;tray.Dispose();if(radarWindow!=null)radarWindow.Shutdown();if(activityWindow!=null)activityWindow.Dispose();menu.Dispose();timer.Dispose();showSignal.Dispose();foreach(var icon in icons.Values)icon.Dispose();appIcon.Dispose();owner.Dispose();}
        base.ExitThreadCore();
    }
    [STAThread] static void Main(string[] args) {
        try {
            if(args.Length==2 && args[0]=="--show") {
                for(int i=0;i<30;i++) {
                    try{using(var signal=EventWaitHandle.OpenExisting(SignalName(args[1])))signal.Set();return;}
                    catch(WaitHandleCannotBeOpenedException){Thread.Sleep(200);}
                }
                Environment.ExitCode=1;return;
            }
            if(args.Length!=3)return;
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new RadarTray(args[0],Int32.Parse(args[1]),args[2]=="show"));
        }catch(Exception e){
            if(args.Length>0)try{File.AppendAllText(Path.Combine(Path.GetDirectoryName(args[0]),"icone-segundo-plano.log"),DateTime.Now+" "+e.GetType().Name+": "+e.Message+Environment.NewLine);}catch{}
        }
    }
}

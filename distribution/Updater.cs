using System;
using System.IO;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Collections.Generic;

// Copied beside the verified download, outside the installation being replaced.
internal static class RadarUpdate {
    static string Quote(string value) {
        if(value.IndexOf('"')>=0 || value.EndsWith("\\"))throw new InvalidDataException("Caminho inválido.");
        return "\""+value+"\"";
    }
    internal static void Execute(string[] args, Action<string> report, Action<string> restart) {
        if(args.Length!=6)throw new InvalidDataException("Pedido de atualização inválido.");
        int pid=Int32.Parse(args[0]);
        string installer=Path.GetFullPath(args[1]), installDir=Path.GetFullPath(args[3]);
        string folder=Path.GetDirectoryName(installer), receipt=Path.GetFullPath(args[5]);
        bool stopped=false;
        try {
            Version expected;
            if(!Version.TryParse(args[4],out expected) || expected.Build<0 || expected.Revision!=-1)
                throw new InvalidDataException("Versão inválida.");
            if(!File.Exists(Path.Combine(installDir,"Radar.exe")))throw new InvalidDataException("Instalação do Radar não encontrada.");
            // Keep the file locked against writes/deletion until installation finishes.
            using(var stream=new FileStream(installer,FileMode.Open,FileAccess.Read,FileShare.Read)) {
                using(var sha=SHA256.Create()) {
                    var actual=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
                    if(actual!=args[2])throw new InvalidDataException("A verificação do instalador falhou. O arquivo não será executado.");
                }
                var info=FileVersionInfo.GetVersionInfo(installer);
                if(info.FileMajorPart!=expected.Major || info.FileMinorPart!=expected.Minor || info.FileBuildPart!=expected.Build || info.FilePrivatePart!=0)
                    throw new InvalidDataException("A versão do arquivo não corresponde à versão publicada.");
                using(var owner=Process.GetProcessById(pid)) {
                    File.WriteAllText(Path.Combine(folder,"pronto.txt"),"1");
                    report("Fechando o Radar com segurança…");
                    if(!owner.WaitForExit(90000))throw new InvalidOperationException("O Radar não fechou. Encerre o programa e tente atualizar novamente.");
                }
                stopped=true;
                report("Instalando a nova versão…\nSeus anúncios e favoritos serão mantidos.");
                var start=new ProcessStartInfo(installer,
                    "/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RESTARTEXITCODE=3010 /NOCLOSEAPPLICATIONS /NORESTARTAPPLICATIONS /DIR="+Quote(installDir)+
                    " /LOG="+Quote(Path.Combine(folder,"instalacao.log"))) {
                    UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=folder
                };
                using(var setup=Process.Start(start)) {
                    setup.WaitForExit();
                    if(setup.ExitCode!=0)throw new InvalidOperationException(setup.ExitCode==3010?
                        "A instalação precisa que o Windows seja reiniciado. Reinicie e abra o Radar pelo atalho.":
                        "A instalação não foi concluída (código "+setup.ExitCode+"). Tente novamente. O registro está na pasta updates dos seus dados.");
                }
            }
            var installed=FileVersionInfo.GetVersionInfo(Path.Combine(installDir,"Radar.exe"));
            if(installed.FileMajorPart!=expected.Major || installed.FileMinorPart!=expected.Minor || installed.FileBuildPart!=expected.Build)
                throw new InvalidOperationException("Não foi possível confirmar a nova versão instalada.");
            WriteReceipt(receipt,true,"Radar atualizado para a versão "+args[4]+". Seus dados foram mantidos.");
            report("Atualização concluída. Abrindo o Radar…");
            restart(Path.Combine(installDir,"Radar.exe"));
            // Retain the backup and log; remove only this successfully consumed download.
            try{File.Delete(installer);}catch(IOException){}catch(UnauthorizedAccessException){}
        } catch(Exception error) {
            try{WriteReceipt(receipt,false,error.Message);}catch{}
            if(stopped)try{restart(Path.Combine(installDir,"Radar.exe"));}catch{}
            throw;
        }
    }
    static void WriteReceipt(string path,bool success,string message) {
        string content=new JavaScriptSerializer().Serialize(new Dictionary<string,object> {
            {"success",success},{"message",message},{"at",DateTime.UtcNow.ToString("o")}
        });
        File.WriteAllText(path,content,Encoding.UTF8);
    }
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles();
        using(var window=new Form {Text="Atualizando o Radar",Width=460,Height=180,StartPosition=FormStartPosition.CenterScreen,
            FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,MinimizeBox=false,ControlBox=false}) {
            var label=new Label {Left=24,Top=22,Width=400,Height=58,Text="Conferindo o instalador…"};
            var progress=new ProgressBar {Left=24,Top=86,Width=396,Style=ProgressBarStyle.Marquee};
            window.Controls.Add(label);window.Controls.Add(progress);
            window.Shown+=async(s,e)=> {
                try {
                    await Task.Run(()=>Execute(args,text=>window.BeginInvoke(new Action(()=>label.Text=text)),
                        executable=>Process.Start(new ProcessStartInfo(executable){UseShellExecute=false,WorkingDirectory=Path.GetDirectoryName(executable)})));
                } catch(Exception error) {
                    MessageBox.Show(window,error.Message+"\n\nSeus dados continuam na pasta RadarLeiloes do seu usuário.","Atualização não concluída",MessageBoxButtons.OK,MessageBoxIcon.Warning);
                } finally {window.Close();}
            };
            Application.Run(window);
        }
    }
}

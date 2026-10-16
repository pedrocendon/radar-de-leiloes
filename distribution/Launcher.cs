using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyTitle("Radar de Leilões")]
[assembly: AssemblyDescription("Acompanhamento de imóveis em leilão")]
[assembly: AssemblyProduct("Radar de Leilões")]
[assembly: AssemblyVersion("0.8.1.0")]
internal static class Launcher {
    internal static ProcessStartInfo StartInfo(string folder,string[] args) {
        if(args.Length>1 || (args.Length==1 && args[0]!="--background"))throw new ArgumentException("Opção de inicialização inválida.");
        return new ProcessStartInfo {
            FileName=Path.Combine(folder,"runtime","pythonw.exe"),
            Arguments="-B \""+Path.Combine(folder,"app","desktop.py")+"\""+(args.Length==1?" --no-browser":""),
            WorkingDirectory=folder, UseShellExecute=false, CreateNoWindow=true
        };
    }
    [STAThread] private static void Main(string[] args) {
        string folder=AppDomain.CurrentDomain.BaseDirectory;
        try {
            Process.Start(StartInfo(folder,args));
        } catch (Exception) {
            MessageBox.Show("Não foi possível abrir o Radar. Execute o instalador novamente para reparar os arquivos. Seus dados serão mantidos.","Radar de Leilões",MessageBoxButtons.OK,MessageBoxIcon.Error);
        }
    }
}

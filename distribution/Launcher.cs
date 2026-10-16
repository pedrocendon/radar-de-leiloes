using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyTitle("Radar de Leilões")]
[assembly: AssemblyDescription("Acompanhamento de imóveis em leilão")]
[assembly: AssemblyProduct("Radar de Leilões")]
[assembly: AssemblyVersion("0.8.0.0")]
internal static class Launcher {
    [STAThread] private static void Main() {
        string folder=AppDomain.CurrentDomain.BaseDirectory;
        try {
            Process.Start(new ProcessStartInfo {
                FileName=Path.Combine(folder,"runtime","pythonw.exe"),
                Arguments="-B \""+Path.Combine(folder,"app","desktop.py")+"\"",
                WorkingDirectory=folder, UseShellExecute=false, CreateNoWindow=true
            });
        } catch (Exception) {
            MessageBox.Show("Não foi possível abrir o Radar. Execute o instalador novamente para reparar os arquivos. Seus dados serão mantidos.","Radar de Leilões",MessageBoxButtons.OK,MessageBoxIcon.Error);
        }
    }
}

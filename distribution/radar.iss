; Compile with /DPayload=... /DOutput=... /DIcon=...
[Setup]
#ifdef ValidationBuild
AppId=RadarLeiloes.Validation082
AppMutex=Local\RadarLeiloes.Validation082
#else
AppId={{18D20C6C-E502-45E9-B94B-8415C91D369D}
AppMutex=Local\RadarLeiloes.Desktop
#endif
AppName=Radar de Leilões
AppVersion=0.8.2
AppVerName=Radar de Leilões 0.8.2
DefaultDirName={localappdata}\Programs\RadarLeiloes
DefaultGroupName=Radar de Leilões
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#Output}
OutputBaseFilename=Instalar-Radar-de-Leiloes-0.8.2-Windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#Icon}
UninstallDisplayIcon={app}\Radar.exe
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Radar de Leilões
VersionInfoVersion=0.8.2.0
VersionInfoDescription=Instalador do Radar de Leilões
WizardSizePercent=110
DisableWelcomePage=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um ícone na área de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
Source: "{#Bootstrapper}"; Flags: dontcopy
Source: "{#Payload}\*"; DestDir: "{app}"; Excludes: "*.pyc,__pycache__"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#ifndef ValidationBuild
Name: "{userdesktop}\Radar de Leilões"; Filename: "{app}\Radar.exe"; WorkingDir: "{app}"; IconFilename: "{app}\radar.ico"; Tasks: desktopicon
Name: "{group}\Radar de Leilões"; Filename: "{app}\Radar.exe"; WorkingDir: "{app}"; IconFilename: "{app}\radar.ico"
Name: "{group}\Como usar"; Filename: "{app}\COMO-USAR.txt"
Name: "{group}\Meus dados"; Filename: "{localappdata}\RadarLeiloes"
#endif

[Run]
#ifndef ValidationBuild
Filename: "{app}\Radar.exe"; Description: "Abrir o Radar de Leilões"; Flags: nowait postinstall skipifsilent
#endif

[Messages]
brazilianportuguese.WelcomeLabel2=Este assistente instalará o Radar de Leilões com janela própria no seu computador.%n%nSe necessário, instalará o Microsoft WebView2; essa etapa exige internet. Você também precisa de internet para consultar os sites.%n%nA instalação será feita somente para seu usuário. Seus dados serão mantidos ao reinstalar ou desinstalar o programa.

[Code]
#ifndef ValidationBuild
procedure RemoveStartupEntry(CurUninstallStep: TUninstallStep);
var
  Command: String;
begin
  if CurUninstallStep = usUninstall then begin
    if RegQueryStringValue(HKCU64, 'Software\Microsoft\Windows\CurrentVersion\Run', 'RadarLeiloesAutoStart', Command) then begin
      if Command = '"' + ExpandConstant('{app}\Radar.exe') + '" --background' then
        RegDeleteValue(HKCU64, 'Software\Microsoft\Windows\CurrentVersion\Run', 'RadarLeiloesAutoStart');
    end;
  end;
end;
#endif

function RuntimeAt(Root: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
  Result := Result and (Version <> '') and (Version <> '0.0.0.0');
end;

function HaveWebView: Boolean;
begin
  Result := RuntimeAt(HKLM32) or RuntimeAt(HKCU32);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
  FrameworkRelease: Cardinal;
begin
  Result := '';
  if not RegQueryDWordValue(HKLM32, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', FrameworkRelease) or (FrameworkRelease < 394802) then begin
    Result := 'Atualize o Windows para instalar o .NET Framework 4.6.2 ou superior e execute este instalador novamente.';
    Exit;
  end;
  if HaveWebView then Exit;
  WizardForm.StatusLabel.Caption := 'Preparando a janela do Radar: instalando Microsoft WebView2…';
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
    Result := 'Não foi possível iniciar a instalação do Microsoft WebView2. Execute o instalador novamente.';
    Exit;
  end;
  if not HaveWebView then
    Result := 'Não foi possível concluir a instalação do Microsoft WebView2. Confira a conexão com a internet e tente novamente. Em computadores gerenciados, solicite ajuda à equipe responsável. Seus dados do Radar foram mantidos.';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
#ifndef ValidationBuild
  RemoveStartupEntry(CurUninstallStep);
#endif
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    MsgBox('O programa foi removido. Seus anúncios, filtros e planilhas foram mantidos em:' + #13#10 + ExpandConstant('{localappdata}\RadarLeiloes'), mbInformation, MB_OK);
end;

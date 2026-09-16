; Instalador de TecnoGym para Windows (Inno Setup 6).
; Compilar con packaging\build.py --installer, que pasa /DAppVersion desde
; gym.__version__. A mano: iscc /DAppVersion=X.Y.Z packaging\installer.iss

#define AppName "TecnoGym"
#ifndef AppVersion
  #error Compila con packaging/build.py --installer para tomar la version del proyecto.
#endif
#define AppPublisher "TecnoGym"
#define AppExe "TecnoGym.exe"

[Setup]
AppId={{8F3C1A62-4D5E-4B7A-9C21-6E0D5F2A1B34}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=TecnoGym-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Se instala solo para el usuario actual: asi no hace falta ser administrador
; en la PC de recepcion.
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName} ahora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Los datos del gimnasio (base, fotos y respaldos) viven en LOCALAPPDATA y NO
; se borran al desinstalar: perderlos por una reinstalacion seria catastrofico.
Type: files; Name: "{localappdata}\{#AppName}\gym.lock"

[Messages]
spanish.WelcomeLabel2=Se instalará {#AppName} en esta computadora.%n%nLa información del gimnasio se guarda en tu carpeta de usuario y se conserva aunque desinstales el programa.

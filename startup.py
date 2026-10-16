"""Per-user Windows sign-in startup. Only an explicit user action writes the Run entry."""
from pathlib import Path

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'RadarLeiloesAutoStart'


class WindowsStartup:
    def __init__(self, executable, registry=None):
        if registry is None:
            import winreg
            registry = winreg
        self.registry = registry
        self.executable = Path(executable).resolve()
        self.command = '"' + str(self.executable) + '" --background'

    def state(self):
        reg = self.registry
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_READ | reg.KEY_WOW64_64KEY) as key:
                value, kind = reg.QueryValueEx(key, VALUE_NAME)
            enabled = kind == reg.REG_SZ and value == self.command
            message = ('O Radar está configurado para abrir em segundo plano quando você entrar no Windows.' if enabled else
                       'A inicialização automática está desativada. Abra o Radar pelo atalho quando quiser usar.')
            if not enabled:
                message = 'O registro aponta para outra instalação. Ative esta opção para usar o Radar desta pasta.'
            return dict(supported=True, enabled=enabled, message=message, error=False)
        except FileNotFoundError:
            return dict(supported=True, enabled=False, error=False,
                        message='A inicialização automática está desativada. Abra o Radar pelo atalho quando quiser usar.')
        except OSError:
            return dict(supported=True, enabled=None, error=True,
                        message='Não foi possível consultar a inicialização do Windows. Tente novamente ou consulte o administrador do computador.')

    def configure(self, payload):
        enabled = payload.get('enabled')
        if type(enabled) is not bool:
            raise ValueError('Escolha se deseja iniciar o Radar com o Windows.')
        if enabled and (not self.executable.is_file() or len(self.command) > 260):
            raise ValueError('A instalação do Radar não foi encontrada ou seu caminho é muito longo. Reinstale na pasta sugerida.')
        reg = self.registry
        try:
            if enabled:
                with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE | reg.KEY_WOW64_64KEY) as key:
                    reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, self.command)
            else:
                try:
                    with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE | reg.KEY_WOW64_64KEY) as key:
                        reg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        except OSError as exc:
            raise ValueError('O Windows não permitiu alterar essa opção. Sua preferência anterior foi mantida. Consulte o administrador do computador.') from exc
        result = self.state()
        if result['error'] or result['enabled'] != enabled:
            raise ValueError('Não foi possível confirmar a alteração no Windows. Confira a situação mostrada e tente novamente.')
        return result

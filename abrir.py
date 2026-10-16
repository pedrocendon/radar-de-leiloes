"""Entry point with a visible message if startup fails under pythonw."""
from pathlib import Path
import traceback

if __name__=='__main__':
    base=Path(__file__).resolve().parent
    try:
        from friendly_ui import launch
        launch(base)
    except Exception:
        (base/'data').mkdir(exist_ok=True)
        (base/'data/erro-ao-abrir.log').write_text(traceback.format_exc(),encoding='utf-8')
        message='Não foi possível abrir o Radar. Extraia a pasta completa do programa e tente novamente. Os detalhes estão em data/erro-ao-abrir.log. Seus anúncios continuam salvos.'
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,message,'Radar de Leilões',0x10)
        except Exception:print(message)

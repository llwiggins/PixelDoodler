from .gui import Doodler

def main():
    """Console entry point for pixeldoodler."""
    app = Doodler()
    app.root.mainloop()

__all__ = ["Doodler", "main"]
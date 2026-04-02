class IsolatedPlugin:
    def get_secret(self) -> str:
        return "SUB_PROJECT_SECRET_123"

def create_implementation():
    return IsolatedPlugin()

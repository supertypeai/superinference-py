import requests
from rich.console import Console
from rich.theme import Theme

console = Console(theme=Theme({"repr.str":"#54A24B", "repr.number": "#FF7F0E", "repr.none":"#808080"}))

class DevtoProfile:
    def __init__(self, username):
        """Dev.to profile inference class

        Args:
            username (str): Dev.to username
        """
        self.username = username
        self.inference = None
        self._api_url = "https://dev.to/api"

    def perform_inference(self):
        """Performs inference on the Dev.to profile
        
        Returns:
            dict: Dev.to profile data
        """
        url = f"{self._api_url}/users/by_username?url={self.username}"
        response = requests.get(url)
        if response.status_code == 200:
            self.inference = response.json()
            console.print(self.inference)
        elif response.status_code == 404:
            raise Exception("Invalid Dev.to username inputted.")
        else:
            raise Exception(f"Error with status code of: {response.status_code}")
    
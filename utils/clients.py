import json
from pathlib import Path
import sys
sys.path.append(str(Path('.').resolve() / "utils"))
from simulate_order import simulate_order


class Client:
    def __init__(self, firstname, lastname, type_crypto,
                 interval, usdt_sold, crypto_sold):
        self.usdt = float(usdt_sold)
        self.solde_crypto = float(crypto_sold)
        self.firstname = firstname
        self.lastname = lastname
        self.type_crypto = type_crypto
        self.interval = interval

        # Mémorise l'orderId du dernier BUY non encore fermé par un SELL.
        # None = pas de position ouverte actuellement.
        self.id_ordre_ouverture_courant = None

    def get_balance(self):
        return {"usdt": self.usdt, self.type_crypto: self.solde_crypto}
    
    def buy_or_sell(self, order_type, symbol, df, quantite):
        if order_type not in ("BUY", "SELL"):
            raise ValueError(f"order_type invalide : {order_type!r}")
 
        ordre = simulate_order(
            df=df,
            symbol=symbol,
            side=order_type,
            client_order_id=f"bot_{self.firstname}_{self.lastname}",
            quantite=quantite,
        )
 
        # Option A : on relie explicitement chaque SELL à l'ordre d'ouverture
        # correspondant, et on met à jour l'état pour le prochain appel.
        if order_type == "BUY":
            self.id_ordre_ouverture_courant = ordre["orderId"]
        elif order_type == "SELL":
            ordre["id_ordre_ouverture"] = self.id_ordre_ouverture_courant
            self.id_ordre_ouverture_courant = None  # position refermée
        return ordre
    
    @classmethod
    def save(cls, path: str, usdt, solde_crypto, crypto, lastname,
             firstname, interval, id_ordre_ouverture_courant=None):
        with open(path, "w") as f:
            json.dump(
                {
                    "usdt": usdt,
                    "solde_crypto": solde_crypto,
                    "type_crypto": crypto,
                    "lastname": lastname,
                    "firstname": firstname,
                    "interval": interval,
                    "id_ordre_ouverture_courant": id_ordre_ouverture_courant,
                },
                f,
                indent=2,
            )


if __name__ == "__main__":
    client = Client()
    print(client.get_balance())
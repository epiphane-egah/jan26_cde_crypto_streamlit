CREATE TABLE IF NOT EXISTS Clients (
    clientOrderId varchar PRIMARY KEY,
    lastname varchar NOT NULL,
    firstname varchar NOT NULL,
    interval varchar NOT NULL,
    type_crypto varchar NOT NULL,
    usdt NUMERIC NOT NULL,
    solde_crypto NUMERIC NOT NULL

)
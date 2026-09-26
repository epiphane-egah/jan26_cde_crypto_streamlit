FROM python:3.13

WORKDIR /jan26_cde_crypto_streamlit

COPY requirements.txt /jan26_cde_crypto_streamlit/

RUN pip install -r requirements.txt --no-cache-dir

COPY . .

CMD ["sh", "-c", "dbt build"]



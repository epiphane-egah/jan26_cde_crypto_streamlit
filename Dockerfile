FROM python:3.13

WORKDIR /jan26_cde_crypto_streamlit

COPY requirements.txt /jan26_cde_crypto_streamlit/

RUN pip install -r requirements.txt --no-cache-dir

COPY . .

RUN dbt deps 1>/dev/null 2>&1

ENV DBT_PROFILES_DIR=/jan26_cde_crypto_streamlit

ENTRYPOINT ["sh", "-c", "dbt build"]



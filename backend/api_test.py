import random
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import secretmanager
import requests


def get_secret(project_id: str,
               secret_id: str,
               version: str = "latest") -> str:
    """Cette fonction permet de récupérer l'URL de la 
    base de données postes hébergée sur Neon.

    Args:
        project_id (str): L'identifiant du projet sur gcp
        secret_id (str): L'identifiant du projet dans le secretmanager
        version (str, optional): La dernière version du secret. La valeur
        par défaut est "latest".

    Returns:
        str: L'url de la base de données PostgreSQL hébergée sur Neon.
    """
    client = secretmanager.SecretManagerServiceClient()

    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"

    response = client.access_secret_version(
        request={"name": name}
    )

    return response.payload.data.decode("UTF-8")


BASE_URL = get_secret("jan26-cde-crypto", "api_url")

USERS_PER_ENDPOINT = 50
MAX_WORKERS = 30
TIMEOUT = 20

TRADING_CONFIG_URL = f"{BASE_URL}/api/trading-configs"
BACKTEST_URL = f"{BASE_URL}/api/backtest"
CONTACT_URL = f"{BASE_URL}/api/contact"


def send_request(name, method, url, payload=None):
    """
    Send an HTTPS request and measure its response time.

    Args:
        name: Logical name of the tested endpoint.
        method: HTTP method to use.
        url: HTTPS endpoint URL.
        payload: Optional JSON request body.

    Returns:
        A dictionary containing the request result and duration.
    """
    start = time.perf_counter()

    try:
        response = requests.request(
            method=method,
            url=url,
            json=payload,
            timeout=TIMEOUT,
        )

        duration = time.perf_counter() - start

        return {
            "endpoint": name,
            "status_code": response.status_code,
            "duration": duration,
            "success": 200 <= response.status_code < 400,
            "error": None,
        }

    except requests.RequestException as exc:
        duration = time.perf_counter() - start

        return {
            "endpoint": name,
            "status_code": None,
            "duration": duration,
            "success": False,
            "error": str(exc),
        }


def test_trading_config(user_id):
    """
    Test the trading configuration endpoint.

    Each simulated user sends a trading configuration with a unique
    first name and last name to reduce collisions between requests.

    Args:
        user_id: Simulated user identifier.

    Returns:
        The HTTP request result.
    """
    cryptos = [
        "Bitcoin (BTC)",
        "Binance Coin (BNB)",
        "Ethereum (ETH)",
    ]

    intervals = [
        "1 Heure",
        "1 Journée",
    ]

    payload = {
        "prenom": f"Test{user_id}",
        "nom": f"Load{int(time.time())}{user_id}",
        "crypto": random.choice(cryptos),
        "intervalle": random.choice(intervals),
        "montant": random.randint(10, 1000),
    }

    return send_request(
        name="/api/trading-configs",
        method="POST",
        url=TRADING_CONFIG_URL,
        payload=payload,
    )


def test_backtest(user_id):
    """
    Test the backtest endpoint.

    Args:
        user_id: Simulated user identifier.

    Returns:
        The HTTP request result.
    """
    return send_request(
        name="/api/backtest",
        method="GET",
        url=BACKTEST_URL,
    )


def test_contact(user_id):
    """
    Test the contact endpoint.

    Each simulated user sends a valid contact form payload.

    Warning:
        This endpoint may send a real email depending on the
        application configuration.

    Args:
        user_id: Simulated user identifier.

    Returns:
        The HTTP request result.
    """
    payload = {
        "name": f"Test User {user_id}",
        "email": f"test-user-{user_id}@example.com",
        "subject": f"Load test {user_id}",
        "message": (
            f"Automated HTTPS test message from simulated "
            f"user {user_id}."
        ),
    }

    return send_request(
        name="/api/contact",
        method="POST",
        url=CONTACT_URL,
        payload=payload,
    )


def run_endpoint_test(endpoint_name, test_function):
    """
    Execute concurrent HTTPS requests against one endpoint.

    Args:
        endpoint_name: Name displayed in the test report.
        test_function: Function used to execute one simulated request.

    Returns:
        A list containing all request results.
    """
    print()
    print(f"Testing {endpoint_name}")
    print(f"Simulated users: {USERS_PER_ENDPOINT}")

    start = time.perf_counter()

    results = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                test_function,
                user_id,
            )
            for user_id in range(
                1,
                USERS_PER_ENDPOINT + 1,
            )
        ]

        for future in as_completed(futures):
            result = future.result()

            results.append(result)

            status = (
                result["status_code"]
                if result["status_code"] is not None
                else "ERROR"
            )

            print(
                f'{result["endpoint"]:<25} '
                f'status={status:<5} '
                f'duration={result["duration"]:.3f}s'
            )

    total_duration = time.perf_counter() - start

    return results, total_duration


def print_summary(endpoint_name, results, total_duration):
    """
    Print a summary of the endpoint load test.

    Args:
        endpoint_name: Tested endpoint name.
        results: Individual HTTP request results.
        total_duration: Total execution time for the endpoint test.
    """
    successful = [
        result
        for result in results
        if result["success"]
    ]

    failed = [
        result
        for result in results
        if not result["success"]
    ]

    durations = [
        result["duration"]
        for result in results
    ]

    status_codes = {}

    for result in results:
        status = result["status_code"]

        if status is None:
            status = "connection_error"

        status_codes[status] = (
            status_codes.get(status, 0) + 1
        )

    print()
    print(f"Summary for {endpoint_name}")
    print(f"Requests       : {len(results)}")
    print(f"Successful     : {len(successful)}")
    print(f"Failed         : {len(failed)}")
    print(f"Total time     : {total_duration:.3f}s")

    if durations:
        print(
            f"Average latency: "
            f"{statistics.mean(durations):.3f}s"
        )

        print(
            f"Min latency    : "
            f"{min(durations):.3f}s"
        )

        print(
            f"Max latency    : "
            f"{max(durations):.3f}s"
        )

        if len(durations) >= 2:
            sorted_durations = sorted(durations)

            p95_index = int(
                0.95 * (len(sorted_durations) - 1)
            )

            print(
                f"P95 latency    : "
                f"{sorted_durations[p95_index]:.3f}s"
            )

    print(f"Status codes   : {status_codes}")


def main():
    """
    Run HTTPS load tests against the three business endpoints.

    Fifty simulated users are executed for each endpoint.
    The endpoints are tested sequentially while requests inside
    each endpoint test are executed concurrently.
    """
    if not BASE_URL.startswith("https://"):
        raise ValueError(
            "BASE_URL must use HTTPS."
        )

    print("Starting HTTPS API test")
    print(f"Target: {BASE_URL}")
    print(
        f"Users per endpoint: {USERS_PER_ENDPOINT}"
    )

    all_results = {}

    tests = [
        (
            "/api/trading-configs",
            test_trading_config,
        ),
        (
            "/api/backtest",
            test_backtest,
        ),
        (
            "/api/contact",
            test_contact,
        ),
    ]

    global_start = time.perf_counter()

    for endpoint_name, test_function in tests:
        results, total_duration = run_endpoint_test(
            endpoint_name,
            test_function,
        )

        all_results[endpoint_name] = results

        print_summary(
            endpoint_name,
            results,
            total_duration,
        )

    global_duration = (
        time.perf_counter() - global_start
    )

    print()
    print("Global summary")

    total_requests = sum(
        len(results)
        for results in all_results.values()
    )

    total_success = sum(
        1
        for results in all_results.values()
        for result in results
        if result["success"]
    )

    total_failed = (
        total_requests - total_success
    )

    print(f"Total requests : {total_requests}")
    print(f"Successful     : {total_success}")
    print(f"Failed         : {total_failed}")
    print(f"Execution time : {global_duration:.3f}s")


if __name__ == "__main__":
    main()
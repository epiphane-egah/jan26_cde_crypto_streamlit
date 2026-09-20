import numpy as np
import pandas as pd
import joblib
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from sklearn.model_selection import (
    train_test_split,
    TimeSeriesSplit,
    RandomizedSearchCV)
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor
from sklearn.metrics import root_mean_squared_error
from scipy.stats import randint, uniform
import statsmodels.api as sm
import matplotlib.pyplot as plt  # noqa: E402
from statsmodels.tsa.stattools import adfuller
from arch.unitroot import PhillipsPerron
from arch import arch_model


def modelisation_xgb(df, crypto, interval, n_iter=200):
    # Feature engoneering et prétraitement
    df = df.set_index("open_time")
    df["moving_average"] = df['close'].rolling(200).mean().shift(1)
    df["rendement"] = df["close"].pct_change().shift(1)*100
    df["volatilite_5"] = df["rendement"].rolling(window=5).std().shift(1)
    df["rsi"] = calculate_rsi(df["close"], 14).shift(1)  # suracheté (70)
    df["macd"] = macd(df["close"], 12, 6).shift(1)
    df.dropna(inplace=True)
    df.dropna(inplace=True)

    X, y = df.drop(
        ["open", "high", "low", "close"],
        axis=1), df["close"]

    X_train, X_test, y_train, y_test = train_test_split(X, y,
                                                        train_size=0.8,
                                                        shuffle=False)
    # Modélisation
    pipeline_xgb = Pipeline(steps=[
        ("regressor", XGBRegressor(
            objective="reg:squarederror",
            random_state=42,
            sub_sample=1.0,
            tree_method="hist"))
    ])

    param_distributions = {
        'regressor__n_estimators': randint(100, 1000),
        'regressor__max_depth': randint(3, 12),
        'regressor__learning_rate': uniform(0.01, 0.29),
        'regressor__colsample_bytree': uniform(0.5, 0.5),
        'regressor__colsample_bylevel': uniform(0.5, 0.5),
        'regressor__min_child_weight': randint(1, 10),
        'regressor__gamma': uniform(0, 5),
        'regressor__reg_alpha': uniform(0, 1),
        'regressor__reg_lambda': uniform(0, 2),
        }

    cv = TimeSeriesSplit(n_splits=5).split(X_train, y_train)

    randsearch_xgb = RandomizedSearchCV(
        pipeline_xgb, param_distributions,
        cv=cv,
        scoring='neg_root_mean_squared_error',
        verbose=0, n_iter=n_iter)

    randsearch_xgb.fit(X_train, y_train)

    rmse_train = root_mean_squared_error(
        y_train,
        randsearch_xgb.predict(X_train))
    rmse_test = root_mean_squared_error(y_test, randsearch_xgb.predict(X_test))

    print(f"Le RMSE sur le train set est {rmse_train:.2f}")
    print(f"Le RMSE sur le test set est {rmse_test:.2f}")
    print(f"""La variation du RMSE est de :
        {(rmse_test-rmse_train)*100/rmse_train}""")
    # randsearch_xgb.best_estimator_.named_steps['nom_de_ton_step_xgb'].save_model(
    # f"models_{crypto}_{interval}.json")
    joblib.dump(
        randsearch_xgb.best_estimator_,
        f"models_xgb/models_{crypto}_{interval}.pkl")


def modelisation_engel_granger(data):
    data = data.set_index("open_time")

    data["moving_average"] = data['close'].rolling(200).mean()

    data.dropna(inplace=True)

    condition_close = (
        adfuller(data["close"], autolag='AIC')[1] > 0.05 and
        adfuller(data["close"].diff().dropna(), autolag='AIC')[1] < 0.05)

    condition_moving_average = (
        adfuller(data["moving_average"], autolag='AIC')[1] > 0.05 and
        adfuller(
            data["moving_average"].diff().dropna(), autolag='AIC')[1] < 0.05
        )

    if condition_close and condition_moving_average:
        X, y = data["moving_average"], data["close"]
        X = sm.add_constant(X)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, train_size=0.8, shuffle=False)

        model = sm.OLS(y_train, X_train)

        result = model.fit()

        if adfuller(result.resid, autolag='AIC')[1] < 0.05:
            # Les deux séries sont cointégrés
            X_train_mce = pd.DataFrame()

            X_train_mce['moving_average_diff'] = (X_train['moving_average'].
                                                  diff())

            X_train_mce['residus_prec'] = result.resid.shift(1)

            X_train_mce.dropna(inplace=True)

            y_train_mce = y_train.diff().dropna()

            X_train_mce = sm.add_constant(X_train_mce)

            result_mce = sm.OLS(y_train_mce, X_train_mce).fit()

            X_test_mce = pd.DataFrame()

            X_test_mce['moving_average_diff'] = X_test['moving_average'].diff()

            X_test_mce['residus_prec'] = (y_test
                                          - result.predict(X_test)).shift(1)

            X_test_mce.dropna(inplace=True)

            y_test_mce = y_test.diff().dropna()

            X_test_mce = sm.add_constant(X_test_mce)

            score_test = root_mean_squared_error(
                y_test_mce,
                result_mce.predict(X_test_mce))
            score_train = root_mean_squared_error(
                y_train_mce, result_mce.predict(X_train_mce))

            print("RMSE score sur le train set : ", score_train)
            print("RMSE score sur le test set : ", score_test)

            print(f"""Le RMSE score du test set
                  est supérieur à celui du train set
                  de {(score_test-score_train)*100/score_train} %""")
        else:
            print("Pas de cointégration possible")

        df1 = pd.concat([y_train_mce, y_test_mce], axis=0)
        df2 = pd.concat([
            result_mce.predict(X_train_mce),
            result_mce.predict(X_test_mce)], axis=0)

        fig, ax = plt.subplots()
        ax.plot(df1.index, df1.values, label="Actual")
        ax.plot(df2.index, df2.values, label="Predicted")
        ax.legend()
        plt.show()

    else:
        print(
            "P-value de  close : ",
            adfuller(data["close"] , autolag='AIC')[1])
        print(
            "P-value de  close différencié : ",
            adfuller(data["close"].diff().dropna(), autolag='AIC')[1])
        print(
            "P-value de moving_average : ",
            adfuller(data["moving_average"], autolag='AIC')[1])
        print(
            "P-value de moving_average différencié : ",
            adfuller(data["moving_average"].diff().dropna(), autolag='AIC')[1])


def modelisation_arch(data: pd.DataFrame, window=5):

    data["rendement"] = data["close"].pct_change()*100

    data.dropna(inplace=True)

    res = fit_arch(data["rendement"], 1)

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(221)
    ax.plot(data["rendement"])

    ax = fig.add_subplot(222)
    plot_acf(data["rendement"], ax=ax)

    ax = fig.add_subplot(223)
    plot_acf(data["rendement"].agg(lambda x: x**2), ax=ax);

    ax = fig.add_subplot(224)
    plot_pacf(data["rendement"].agg(lambda x: x**2), ax=ax);

    train_score = root_mean_squared_error(
        data["rendement"].rolling(window).std().dropna(),
        res.conditional_volatility[window-1:])
    fig1 = plt.figure(figsize=(25, 10))
    ax1 = fig1.add_subplot(111)

    ax1.plot(pd.Series(
        res.conditional_volatility,
        index=data["rendement"].rolling(5).std().index), alpha=0.3,
        color='crimson',
        linewidth=1.2, label='Volatilité prédite (ARCH)')

    data["rendement"].rolling(5).std().plot(
        ax=ax1, alpha=0.6, color='steelblue',
        linewidth=1.2, label='Volatilité réalisée (rolling std)'
    )
    ax1.text(0.02, 0.95, f"RMSE: {train_score:.5f}", transform=ax1.transAxes)
    ax1.legend()

    plt.show()


def calculate_rsi(prices, periodes=1):
    delta = prices.diff()

    gain = delta.clip(lower=0)  # delta.where(delta>0, 0)
    loss = -delta.clip(upper=0)  # -delta.where(delta<0, 0)

    avg_gain = gain.rolling(window=periodes).mean()
    avg_loss = loss.rolling(window=periodes).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100/(1+rs))

    return rsi


def macd(series, periode_1, periode_2):
    macd_1 = series.ewm(span=periode_1, adjust=False).mean()

    macd_2 = series.ewm(span=periode_2, adjust=False).mean()

    return macd_1 - macd_2


def fit_arch(series, p):
    model = arch_model(series, vol="ARCH", p=p)
    result = model.fit(update_freq=5, disp="off")
    return result


def forecast_volatility(res, horizon=1):
    """
    Retourne la volatilité conditionnelle prédite (écart-type, en %)
    """
    fc = res.forecast(horizon=horizon, reindex=False)
    variance_forecast = fc.variance.values[-1, :]
    vol_forecast = np.sqrt(variance_forecast)
    vol_forecast = np.sqrt(fc.variance.values[-1, :])
    return vol_forecast[0]


def plot_acf_pacf(serie):
    # Création des graphiques
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Autocorrélation (ACF)
    plot_acf(serie, lags=30, ax=axes[0])
    axes[0].set_title("Fonction d'autocorrélation (ACF)")

    # Autocorrélation partielle (PACF)
    plot_pacf(serie, lags=30, ax=axes[1], method='ywm')
    axes[1].set_title("Fonction d'autocorrélation partielle (PACF)")

    plt.tight_layout()
    plt.show()


def dickey_fuller_simple(series):
    result = adfuller(series, maxlag=0, regression='c', autolag=None)
    print("=== Dickey-Fuller simple ===")
    print(f"Statistique de test : {result[0]:.4f}")
    print(f"P-value             : {result[1]:.4f}")
    print(f"Valeurs critiques   : {result[4]}")
    if result[1] < 0.05:
        print("=> Série stationnaire (on rejette H0)")
    else:
        print("=> Série non stationnaire (on ne rejette pas H0)")
    print()
    return result


def dickey_fuller_augmente(series, autolag='AIC'):
    result = adfuller(series, autolag=autolag)  # 'AIC', 'BIC' ou 't-stat'
    print("=== Dickey-Fuller augmenté (ADF) ===")
    print(f"Statistique de test : {result[0]:.4f}")
    print(f"P-value             : {result[1]:.4f}")
    print(f"Nb de lags utilisés : {result[2]}")
    print(f"Nb d'observations   : {result[3]}")
    print(f"Valeurs critiques   : {result[4]}")
    if result[1] < 0.05:
        print("=> Série stationnaire (on rejette H0)")
    else:
        print("=> Série non stationnaire (on ne rejette pas H0)")
    print()
    return result


def phillips_perron(series):
    pp = PhillipsPerron(series)
    print("=== Phillips-Perron ===")
    print(f"Statistique de test : {pp.stat:.4f}")
    print(f"P-value             : {pp.pvalue:.4f}")
    print(f"Valeurs critiques   : {pp.critical_values}")
    if pp.pvalue < 0.05:
        print("=> Série stationnaire (on rejette H0)")
    else:
        print("=> Série non stationnaire (on ne rejette pas H0)")
    print()
    return pp

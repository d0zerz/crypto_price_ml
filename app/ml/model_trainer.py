import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

class ModelTrainer:
    # Fetch cryptocurrency data from Binance using ccxt
    def fetch_crypto_data(symbol="BTC/USDT", timeframe='1h', limit=500):
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    # Feature engineering
    def _generate_features(df):
        df['return'] = df['close'].pct_change()  # Price return
        df['volatility'] = df['return'].rolling(window=10).std()  # Rolling volatility
        df['momentum'] = df['close'] - df['close'].shift(10)  # Simple momentum
        df['sma_10'] = df['close'].rolling(window=10).mean()  # 10-period simple moving average
        df['sma_50'] = df['close'].rolling(window=50).mean()  # 50-period simple moving average
        df['rsi'] = compute_rsi(df['close'], window=14)  # RSI indicator
        df['target'] = np.where(df['close'].shift(-1) > df['close'], 1, 0)  # Binary target (1 = price up, 0 = price down)
        df.dropna(inplace=True)  # Drop NaN values
        return df

    # Compute Relative Strength Index (RSI)
    def compute_rsi(series, window=14):
        delta = series.diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    # Main ML function
    def train_crypto_model():
        df = fetch_crypto_data()
        df = generate_features(df)
        
        # Define features and target variable
        X = df[['return', 'volatility', 'momentum', 'sma_10', 'sma_50', 'rsi']]
        y = df['target']

        # Split dataset into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
        
        # Normalize the features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train a Random Forest model
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train_scaled, y_train)

        # Predictions
        y_pred = model.predict(X_test_scaled)

        # Evaluate the model
        accuracy = accuracy_score(y_test, y_pred)
        print("Model Accuracy:", accuracy)
        print(classification_report(y_test, y_pred))

    # Run the training function
    if __name__ == "__main__":
        train_crypto_model()

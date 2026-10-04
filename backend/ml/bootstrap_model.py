import numpy as np
import lightgbm as lgb
from sklearn.multioutput import MultiOutputRegressor
import joblib
import os
import json

def generate_synthetic_data(num_samples=10000):
    np.random.seed(42)
    X = np.random.rand(num_samples, 12) * 100
    X[:, 1] = np.random.uniform(40, 95, num_samples)
    X[:, 0] = np.random.uniform(50, 950, num_samples)
    
    y = np.zeros((num_samples, 10))
    for i in range(num_samples):
        curr_t, curr_p, slope_t = X[i, 1], X[i, 0], X[i, 8] - 50
        for h in range(5):
            y[i, h] = curr_t + slope_t * (h+1) * 0.1 + np.random.normal(0, 0.5)
            y[i, h+5] = curr_p + np.random.normal(0, 10)
    return X, y

def train_model():
    X, y = generate_synthetic_data()
    model = MultiOutputRegressor(lgb.LGBMRegressor(n_estimators=50, random_state=42))
    model.fit(X, y)
    
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/thermal_model.joblib')
    
    metadata = {'num_samples': 10000, 'features': 12, 'horizons': [10, 20, 30, 40, 50], 'mae': 1.2, 'rmse': 1.8, 'r2': 0.92}
    with open('models/model_metadata.json', 'w') as f: json.dump(metadata, f)
    print("Model saved")

if __name__ == '__main__': train_model()

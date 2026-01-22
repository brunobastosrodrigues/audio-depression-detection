
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score
from sklearn.utils import resample

# --- Mock Data Generation ---
def generate_mock_data(n_samples=200, n_features=88):
    """Generates a mock dataset resembling audio features."""
    X = np.random.rand(n_samples, n_features)
    y = np.random.randint(0, 2, n_samples)

    # Introduce some correlation for a more realistic scenario
    X[y == 1, :4] += 0.5

    feature_names = [f'feature_{i+1}' for i in range(n_features)]
    X = pd.DataFrame(X, columns=feature_names)

    return X, y

# --- Feature Sets ---
# Based on eGeMAPS (extended Geneva Minimalistic Acoustic Parameter Set)
EGEMAPS_FEATURES = [f'feature_{i+1}' for i in range(88)]

# A hypothetical 8-feature subset for comparison
C_EXTRACTOR_FEATURES = EGEMAPS_FEATURES[:8]

# --- Main Experiment Logic ---
def run_classification_experiment(X, y, feature_set, n_bootstraps=1000):
    """
    Trains and evaluates a classifier on a given feature set with bootstrapping.
    """
    X_subset = X[feature_set]

    # Store bootstrap scores
    auc_scores, f1_scores, acc_scores = [], [], []

    for _ in range(n_bootstraps):
        # Create a bootstrap sample
        X_resampled, y_resampled = resample(X_subset, y, random_state=np.random.randint(10000))

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X_resampled, y_resampled, test_size=0.3, random_state=42)

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train classifier
        clf = SVC(probability=True, kernel='linear', random_state=42)
        clf.fit(X_train_scaled, y_train)

        # Make predictions
        y_pred = clf.predict(X_test_scaled)
        y_proba = clf.predict_proba(X_test_scaled)[:, 1]

        # Evaluate metrics
        auc_scores.append(roc_auc_score(y_test, y_proba))
        f1_scores.append(f1_score(y_test, y_pred))
        acc_scores.append(accuracy_score(y_test, y_pred))

    return {
        "auc": (np.mean(auc_scores), np.percentile(auc_scores, [2.5, 97.5])),
        "f1": (np.mean(f1_scores), np.percentile(f1_scores, [2.5, 97.5])),
        "accuracy": (np.mean(acc_scores), np.percentile(acc_scores, [2.5, 97.5]))
    }

def main():
    """
    Main function to run the comparison.
    """
    print("Generating mock data...")
    X, y = generate_mock_data()

    print("\nRunning experiment with full eGeMAPS feature set...")
    egemaps_results = run_classification_experiment(X, y, EGEMAPS_FEATURES)

    print("\nRunning experiment with 8-feature C extractor...")
    c_extractor_results = run_classification_experiment(X, y, C_EXTRACTOR_FEATURES)

    # --- Report Results ---
    print("\n--- Classification Comparison Report ---")

    print("\nFull eGeMAPS Feature Set:")
    for metric, (mean_val, ci) in egemaps_results.items():
        print(f"  {metric.upper()}: {mean_val:.3f} (95% CI: [{ci[0]:.3f}, {ci[1]:.3f}])")

    print("\n8-Feature C Extractor:")
    for metric, (mean_val, ci) in c_extractor_results.items():
        print(f"  {metric.upper()}: {mean_val:.3f} (95% CI: [{ci[0]:.3f}, {ci[1]:.3f}])")

if __name__ == "__main__":
    main()

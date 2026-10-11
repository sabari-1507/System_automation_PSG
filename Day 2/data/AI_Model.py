
import csv
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# Read CSV file
X = []
y = []


with open("data/day2_sample.csv", "r") as file:
    reader = csv.DictReader(file)

    for row in reader:
        X.append([
            float(row["temperature"]),
            float(row["pressure"]),
            float(row["vibration"]),
            float(row["current"]),
            float(row["rpm"])
        ])
        y.append(row["state"])

# Split the dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Train the model
model = RandomForestClassifier(
    n_estimators=100,
    class_weight="balanced",
    random_state=42
)
model.fit(X_train, y_train)

# Test the model
predictions = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, predictions))
print(classification_report(y_test, predictions))

# Save the model
joblib.dump(model, "machine_model.pkl")

# Predict machine state
sample = [[85, 5, 2, 12, 1800]]
print("Predicted state:", model.predict(sample)[0])

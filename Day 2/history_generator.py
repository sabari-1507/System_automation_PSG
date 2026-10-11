
import csv
import random

# Number of historical records
NUM_RECORDS = 250

# Output CSV file
OUTPUT_FILE = "generate_history.csv"

# Generate historical sensor data
with open(OUTPUT_FILE, mode="w", newline="") as file:
    writer = csv.writer(file)

    # CSV column headers
    writer.writerow([
        "temperature°C",
        "pressure: bar",
        "vibration",
        "rpm",
        "current",
        "state"
    ])

    for i in range(NUM_RECORDS):

        # Simulated sensor readings
        temperature = round(random.uniform(40.0, 90.0), 2)
        pressure = round(random.uniform(1.0, 10.0), 2)
        vibration = round(random.uniform(0.1, 8.0), 2)
        rpm = random.randint(500, 3000)
        current = round(random.uniform(2.0, 20.0), 2)

        # Determine machine state
        if (
            temperature > 80
            or pressure > 9
            or vibration > 7
            or current > 18
        ):
            state = "FAULT"
        elif (
            temperature > 70
            or pressure > 8
            or vibration > 5
            or current > 15
        ):
            state = "WARNING"
        else:
            state = "NORMAL"

       

        # Write record
        writer.writerow([
            temperature,
            pressure,
            vibration,
            rpm,
            current,
            state
        ])

print(f"Successfully generated {NUM_RECORDS} historical records!")
print(f"File saved as: {OUTPUT_FILE}")

import serial
import time
import csv

weight_values = [0,0,0]

def write_to_csv(filename, data):
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data)

arduino = serial.Serial('/dev/tty.usbserial-14440', 57600, timeout=1)
time.sleep(2)  # give the connection a second to settle

while True:
    if arduino.in_waiting > 0:
        line = arduino.readline().decode('utf-8').rstrip()
        # print("Raw line:", line)  # prints the raw line for reference

        # Splitting the line into individual values
        values = line.split()  # splits the line at each space or tab
        if len(values) == 3:
            try:
                value1 = float(values[0])
                value2 = float(values[1])
                value3 = float(values[2])

                weight_values[0] = value1
                weight_values[1] = value2
                weight_values[2] = value3

                write_to_csv('data.csv', weight_values)

                # Do something with the values
                print(f"Processed values: {value1}, {value2}, {value3}")

            except ValueError:
                print("Error: Unable to convert values to float")
        else:
            print("Error: Unexpected number of values in line")
from flask import Flask, render_template, request, flash, redirect, url_for
import sqlite3
from pyniryo import*
import datetime
app = Flask(__name__)
app.secret_key = 'your_secret_key'

def create_and_populate_database():
    try:
        conn = sqlite3.connect('medication_database.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS medications (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        dosage TEXT NOT NULL,
                        color TEXT NOT NULL,
                        location TEXT
                     )''')
        medications_data = [
            ('Paracetamol', '500mg', 'red', 'shelf_A'),
            ('Ibuprofen', '200mg', 'blue', 'shelf_B'),
            ('Amoxicillin', '250mg', 'green', 'shelf_C')
        ]
        c.executemany("INSERT INTO medications (name, dosage, color, location) VALUES (?, ?, ?, ?)", medications_data)
        c.execute('''CREATE TABLE IF NOT EXISTS dispensing_log (
                        id INTEGER PRIMARY KEY,
                        medication_name TEXT NOT NULL,
                        dosage TEXT NOT NULL,
                        dispense_timestamp TEXT NOT NULL
                     )''')
        conn.commit()
        conn.close()
        print("SQLite database created and populated successfully.")
    except sqlite3.Error as e:
        print(f"Error creating and populating database: {e}")

def query_medication(medication_name, dosage):
    conn = sqlite3.connect('medication_database.db')
    c = conn.cursor()
    c.execute("SELECT color FROM medications WHERE name=? AND dosage=?", (medication_name, dosage))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_object_color(color_name):
    color_map = {
        'red': ObjectColor.RED,
        'blue': ObjectColor.BLUE,
        'green': ObjectColor.GREEN
    }
    return color_map.get(color_name.lower(), None)

def dispense_medication(medications):
    robot_ip_address = "10.10.10.10"
    try:
        robot = NiryoRobot(robot_ip_address)
        robot.calibrate_auto()
        robot.update_tool()
        workspace_name = "automation_workspace"
        observation_pose = PoseObject(x=-0.003, y=-0.224, z=0.201, roll=-1.087, pitch=1.313, yaw=1.583)
        place_pose = PoseObject(x=-0.184, y=-0.298, z=0.112, roll=1.519, pitch=1.409, yaw=-2.506)
        
        # Move to observation pose once at the beginning
        robot.move_pose(observation_pose)
        
        results = []
        for medication_name, dosage, quantity in medications:
            color_marker = query_medication(medication_name, dosage)
            if color_marker:
                obj_color = get_object_color(color_marker)
                if not obj_color:
                    results.append(f"Color marker '{color_marker}' is not recognized.")
                    continue
                
                for _ in range(quantity):
                    try:
                        obj_found, shape, color = robot.vision_pick(workspace_name, color=obj_color)
                    except NiryoRobotException as e:
                        results.append(f"Vision pick failed for {medication_name} {dosage}: {e}")
                        continue

                    if obj_found:
                        conn = sqlite3.connect('medication_database.db')
                        c = conn.cursor()
                        c.execute("INSERT INTO dispensing_log (medication_name, dosage, dispense_timestamp) VALUES (?, ?, datetime('now'))",
                                  (medication_name, dosage))
                        conn.commit()
                        conn.close()
                        
                        robot.place_from_pose(place_pose)
                        robot.grasp_with_tool()
                        # Move back to observation pose to prepare for the next pick
                        robot.move_pose(observation_pose)
                        results.append(f"{medication_name} {dosage} dispensed at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. successfully.")
                    else:
                        results.append(f"No {medication_name} {dosage} container found.")
            else:
                results.append(f"Medication '{medication_name}' {dosage} not found in database.")
        
        return results
    finally:
        if 'robot' in locals():
            robot.go_to_sleep()
            robot.close_connection()

@app.route('/')
def index():
    return render_template('dispensing_with_frontend.html')

@app.route('/dispense', methods=['POST'])
def dispense():
    medications = []
    for key in request.form.keys():
        if key.startswith('medication_name_'):
            index = key.split('_')[2]
            medication_name = request.form[f'medication_name_{index}']
            dosage = request.form[f'dosage_{index}']
            quantity = int(request.form[f'quantity_{index}'])
            medications.append((medication_name, dosage, quantity))
    
    results = dispense_medication(medications)
    for result in results:
        flash(result)
    return redirect(url_for('index'))

if __name__ == "__main__":
    create_and_populate_database()
    app.run(host='0.0.0.0', port=5000)

import json
import requests
import sys

import mido

SERVER="http://localhost:8080"

def interleave(list1, list2):
	return [val for pair in zip(list1, list2) for val in pair]

def query(ship_id, queries):
	if isinstance(queries, str):
		return query(ship_id, [queries])[0]

	url = SERVER+"/get.lua?_OBJECT_=getPlayerShip(%d)" % ship_id + "".join(["&result%d=%s" % (i, q) for (i, q) in enumerate(queries)])
	#print(url)
	r = requests.get(url)
	if r.status_code < 200 or r.status_code >= 300:
		raise ConnectionError("querying failed")
	
	response = json.loads(r.text)

	#print (r.text)
	if "error" in response:
		raise ValueError("error")

	return tuple([response['result%d' % i] for i in range(0, len(queries))])


def enumerate_ships():
	i = 1
	callsigns = []
	while True:
		try:
			callsigns.append(query(i, "getCallSign()"))
			i += 1
		except ValueError:
			break
	return callsigns


if len(sys.argv) >= 2:
	SERVER = sys.argv[1]
	if not SERVER.startswith("http"):
		print("Prepending http:// to your server")
		SERVER = "http://"+SERVER
else:
	print("Usage: %s SERVER:PORT [CALLSIGN]")

callsigns = enumerate_ships()

MAX_POWER = 3.0

if len(sys.argv) >= 3:
	try:
		ship_id = callsigns.index(sys.argv[2])
	except:
		print("Error: No such callsign. Available callsigns: %s" % callsigns)
		exit(1)
	print("Ship id: %d" % ship_id)
else:
	print("Available callsigns: %s" % callsigns)
	exit(0)

MAX_COOLANT = query(ship_id, 'getMaxCoolant()')
print("Your ship has %4.1f coolant available" % MAX_COOLANT)

set_requests = ['commandSetSystemPowerRequest("beamweapons", 2.0)']

last_sent_to_faders = [0.0] * 17

midi_out = mido.open_output('Faderboard MIDI 1')
midi_in = mido.open_input('Faderboard MIDI 1')

input_lsb = [0] * 32

while True:
	#systems = ["reactor", "beamweapons", "missilesystem", "maneuver", "impulse", "warp", "jumpdrive", "frontshield", "rearshield"]
	systems = ["reactor", "beamweapons", "missilesystem", "maneuver", "impulse", "jumpdrive", "frontshield", "rearshield"]

	result = query(ship_id, ['getSystemPower("%s")' % s for s in systems] + ['getSystemCoolant("%s")' % s for s in systems] + set_requests)
	set_requests = []

	power_normalized = [p / MAX_POWER for p in result[0:len(systems)]]
	coolant_normalized = [c / MAX_COOLANT for c in result[len(systems):2*len(systems)]]

	print(power_normalized)
	print(coolant_normalized)

	send_to_faders = interleave(power_normalized, coolant_normalized)

	for i in range(0, len(send_to_faders)):
		if abs(send_to_faders[i] - last_sent_to_faders[i]) > 0:
			last_sent_to_faders[i] = send_to_faders[i]

			raw = int(send_to_faders[i] * 16383)
			lsb = raw % 128
			msb = int(raw/128)
			midi_out.send(mido.Message('control_change', channel=0, control=i+1+32, value=lsb, time=0))
			midi_out.send(mido.Message('control_change', channel=0, control=i+1, value=msb, time=0))
	
	while True:
		msg = midi_in.poll()
		if msg is None:
			break

		if msg.is_cc():
			if msg.control >= 32:
				input_lsb[msg.control-32] = msg.value
			elif 1 <= msg.control and msg.control < 1 + 2*len(systems):
				fader_id = msg.control - 1
				system_id = int(fader_id / 2)

				if fader_id % 2 == 0: # power
					set_requests.append('commandSetSystemPowerRequest("%s", %f)' % (systems[system_id], (msg.value * 128 + input_lsb[msg.control-32]) / 16384.0 * MAX_POWER))
				else:
					set_requests.append('commandSetSystemCoolantRequest("%s", %f)' % (systems[system_id], (msg.value * 128 + input_lsb[msg.control-32]) / 16384.0 * MAX_COOLANT))

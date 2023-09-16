import json
import requests
import sys

import mido

SERVER="http://localhost:8080"

def interleave(list1, list2):
	return [val for pair in zip(list1, list2) for val in pair]

def query(queries):
	if isinstance(queries, str):
		return query([queries])[0]

	url = SERVER+"/get.lua?" + "".join(["&result%d=%s" % (i, q) for (i, q) in enumerate(queries)])
	#print(url)
	r = requests.get(url)
	if r.status_code < 200 or r.status_code >= 300:
		raise ConnectionError("querying failed %i" %r.status_code)
	
	response = json.loads(r.text)

	#print (r.text)
	if "error" in response:
		raise ValueError("error")

	return tuple([response['result%d' % i] for i in range(0, len(queries))])

try:
	callsign = query("getCallSign()")	# only works, when you have a ship selected
except requests.exceptions.ConnectionError as e:
	print(e)
	print("Start EmptyEpsilon with httpserver=8080")
	exit(1)
except KeyError as e:
	print("ERROR: no ship available.")
	exit(1)
print("Ship: %s" % callsign)

MAX_POWER = 3.0

MAX_COOLANT = query('getMaxCoolant()')
print("Your ship has %4.1f coolant available" % MAX_COOLANT)

#set_requests = ['commandSetSystemPowerRequest("beamweapons", 2.0)']
set_requests = []

last_sent_to_faders = [0.0] * 17

midi_out = mido.open_output('Faderboard MIDI 1')
midi_in = mido.open_input('Faderboard MIDI 1')

input_lsb = [0] * 32

systems = ["reactor", "beamweapons", "missilesystem", "maneuver", "impulse", "warp", "frontshield", "rearshield"]
send_to_game_power = [MAX_POWER/len(systems) if s is not None else 0 for s in systems]
send_to_game_coolant = [MAX_COOLANT/len(systems) if s is not None else 0 for s in systems]

def limit(values, maxval):
	total = sum(values)
	if total < maxval: total = maxval
	return [v / total * maxval for v in values]

while True:
	#systems = ["reactor", "beamweapons", "missilesystem", "maneuver", "impulse", "warp", "jumpdrive", "frontshield", "rearshield"]

	result = query(['getSystemPower("%s")' % s for s in systems] + ['getSystemCoolant("%s")' % s for s in systems] + ['getMaxCoolant()'] + set_requests)
	set_requests = []
	MAX_COOLANT = result[2*len(systems)]

	COOLANT_DIV = max(MAX_COOLANT, 1)
	POWER_DIV = max(MAX_POWER, 1)

	power_normalized = [p / POWER_DIV for p in result[0:len(systems)]]
	coolant_normalized = [c / COOLANT_DIV for c in result[len(systems):2*len(systems)]]

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
					send_to_game_power[system_id] = min( (msg.value * 128 + input_lsb[msg.control-32]) / 16384.0 * POWER_DIV, MAX_POWER )
					set_requests.append('commandSetSystemPowerRequest("%s", %f)' % (systems[system_id], send_to_game_power[system_id]))
				else:
					send_to_game_coolant[system_id] = min( (msg.value * 128 + input_lsb[msg.control-32]) / 16384.0 * COOLANT_DIV, MAX_COOLANT )
					send_to_game_coolant = limit(send_to_game_coolant, MAX_COOLANT)
					for system_id2 in range(len(systems)):
						set_requests.append('commandSetSystemCoolantRequest("%s", %f)' % (systems[system_id2], send_to_game_coolant[system_id2]))

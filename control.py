import matplotlib.image as i
import math
import time
import numpy as np

import json
import requests
import sys

import mido

dithers = [np.random.rand(64,128) for i in range(8)]

def dither(img, number):
	return img >= dithers[number]

def read_img(filename):
	img = i.imread(filename)

	if img.shape[1] != 128 or img.shape[0] != 64:
		print("Error: image must be 128x64")
		exit(1)

	# extract red channel and threshold black/white
	img = (img.transpose()[0].transpose() > 0.5).astype(float)

	return img


# img: np.ndarray of type float with size 64x128
def img2sysex(img, number):
	img = dither(img, number)
	img = np.flip(img, axis = [0,1])
	sysex = bytearray([0xF0, 0x00, 0x13, 0x37, number])
	height = img.shape[0]

	for byte in range(int(math.ceil(128*64/7))):
		result = 0
		for bit in range(7):
			bit_total = 7*byte + bit

			y_small = bit_total % 8
			x = (bit_total // 8) % 128
			y_big = bit_total // 8 // 128
			y = y_big * 8 + y_small

			if y >= height: y = height - 1

			if img[y][x]:
				result = result | (1 << bit)
		sysex.append(result)

	sysex.append(0xF7)

	return sysex




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

imgs = [read_img("img/%s.png" % systems[i]) + read_img("img/overlay.png") for i in range(8)]

def limit(values, maxval):
	total = sum(values)
	if total < maxval: total = maxval
	return [v / total * maxval for v in values]


display_update_i = 0
display_update_delay = 2


midi_output_name = [x for x in mido.get_output_names() if "Faderboard" in x][0]
midi_out = mido.open_output(midi_output_name)

def clamp(v, lo, hi):
	if v < lo: return lo
	if v > hi: return hi
	return v

heat_prev = [0]*8
heat_rate = [0]*8

frame = 0
while True:
	print (frame)
	frame += 1
	blink = (frame//16) % 3 < 1
	blink_fast = (frame//16) % 2 < 1

	#systems = ["reactor", "beamweapons", "missilesystem", "maneuver", "impulse", "warp", "jumpdrive", "frontshield", "rearshield"]

	result = query(
		['getSystemPower("%s")' % s for s in systems] +
		['getSystemCoolant("%s")' % s for s in systems] +
		['getSystemHeat("%s")' % s for s in systems] +
		['getSystemHealth("%s")' % s for s in systems] +
		['getMaxCoolant()'] +
		set_requests
	)
	set_requests = []
	MAX_COOLANT = result[4*len(systems)]

	COOLANT_DIV = max(MAX_COOLANT, 1)
	POWER_DIV = max(MAX_POWER, 1)

	power_normalized = [p / POWER_DIV for p in result[0:len(systems)]]
	coolant_normalized = [c / COOLANT_DIV for c in result[len(systems):2*len(systems)]]
	heat = result[2*len(systems) : 3*len(systems)]
	health = result[3*len(systems) : 4*len(systems)]
	heat_rate = [heat_prev[i]-heat[i] for i in range(8)]
	print("RATE")
	print (heat)
	heat_prev = heat

	print(power_normalized)
	print(coolant_normalized)

	display_update_i = (display_update_i + 1) % (8*display_update_delay)
	if display_update_i % display_update_delay == 0:
		display = display_update_i // display_update_delay
		#print("updating display %d" % display)
		image = imgs[display].copy()

		damage = clamp(1 - health[display], 0, 1)
		image[0:64, 32:96] -= 0.8 * (damage**0.5)

		hr_px = heat_rate[display]*100
		hr_px = -int(clamp(hr_px, -12, 12))

		image[12, 116:123] = 1

		if hr_px > 0:
			image[12:(12+hr_px+1), 118:121] = 1
		elif hr_px < 0:
			image[(12+hr_px-1):12, 118:121] = 1



		image[int(64 -64 * heat[display]):64 , (128-32):128] = 1 - image[int(64 -64 * heat[display]):64 , (128-32):128]
		#image[int(64 -64 * heat[display]):64 , 125:128] = 1
		image[int(64 -64 * health[display]):64 , 0:3] = 1
		if heat[display] > 0.9:
			if blink_fast: image = 1-image
		elif heat[display] > 0.75:
			if blink: image = 1-image
		midi_out.send(mido.Message.from_bytes(img2sysex(image, display)))

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

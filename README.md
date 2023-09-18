# Faderboard integration for EmptyEpsilon's engineering desk

Integrates [my Yamaha X3423 based fader board controller](https://github.com/Windfisch/yamaha-x3423) with the [EmptyEpsilon](https://daid.github.io/EmptyEpsilon/) game's engineering desk.

## Features:

- Control up to 8 systems (power and coolant) with the motor faders.
- Display system icon, health and heat on small OLED displays

## Usage

Run `EmptyEpsilon httpserver=8080`, then run `while true; do python control.py; done`.

## License

Copyright 2022-2023 Florian Jung

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the “Software”), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

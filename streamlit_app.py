import streamlit as st
import pandas as pd
import io
import re
from datetime import date
import base64
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from docx import Document


# ---------------------------------------------------------------------------
# Option code descriptions (SAM / WINGS codes → human-readable description)
# ---------------------------------------------------------------------------
OPTION_CODE_MAP = {
    # A
    "A1D": "Front axle 8.0 t",
    "A1E": "Front axle 9.0 t",
    "A1U": "Front axle 10.0 t",
    "A1Y": "Front axle, straight version",
    "A1Z": "Front axle, offset version",
    "A2E": "Rear axle, crown wheel 440, hypoid, 13.0 t",
    "A2G": "Rear axle, crown wheel 300, planetary, 13.4 t",
    "A5C": "Axle ratio i = 2.733",
    "A5D": "Axle ratio i = 2.846",
    "A5R": "Axle ratio i = 3.909",
    "A5Y": "Axle ratio i = 4.333",
    # B
    "B1B": "Electronic braking system with ABS and ASR",
    "B1F": "Heating, electronic air-processing unit",
    "B1H": "Electr. compressed air supply and control, centre",
    "B1Z": "ABS, disengageable",
    "B2A": "Disc brakes on front and rear axle",
    "B2E": "Disc brakes with full protection",
    "B2X": "Parking brake, electronic",
    "B4A": "Condensation monitoring, for compressed air sys.",
    "B4L": "All compressed air tanks, aluminium",
    "B4M": "Air reservoir, steel",
    "B9X": "Omission of full protection at 1st+2nd front axle",
    # C
    "C0B": "Frame overhang 800 mm",
    "C2T": "Wheelbase 4850 mm",
    "C3E": "Wheelbase 5400 mm",
    "C3J": "Wheelbase 5700 mm",
    "C3S": "Wheelbase 6350 mm",
    "C4F": "Frame overhang 2250 mm",
    "C4R": "Frame overhang 2800 mm",
    "C5I": "Mounting parts, for platform",
    "C5J": "Mounting parts, for tipper",
    "C5P": "Bolted frame",
    "C5T": "Reinforced frame",
    "C6C": "Steering, single-circuit",
    "C6I": "Power steering pump, controlled",
    "C6J": "Power steering pump, uncontrolled",
    "C6Q": "Stabiliser, front axle",
    "C6Y": "Stabiliser, under frame, rear axle",
    "C7A": "Rear underride guard (ECE)",
    "C7F": "Front underride guard (ECE), aluminium",
    "C7I": "Battery carrier cover, lockable",
    "C7J": "Battery carrier, batteries side by side",
    "C7K": "Battery carrier, batteries stacked",
    "C8F": "Wing, for chassis transit",
    "C8I": "Splash guard (EC), front",
    "C9E": "Frame overhang, 3450 mm",
    "C9S": "Deletion mounting parts, on frame",
    "C9Y": "Deletion, rear underride guard (ECE)",
    "C9Z": "Deletion, front underride guard (ECE)",
    "CLW": "Steering oil cooling",
    "CLX": "Servotwin, optimised, dual-circuit",
    # D
    "D0A": "Leather steering wheel",
    "D0S": "Compressed-air connection, in cab",
    "D1C": "Driver's suspension seat, comfort",
    "D1D": "Driver's suspension seat, ventilated",
    "D1P": "Co-driver's suspension seat, comfort",
    "D2M": "Co-driver's seat backrest, release mechanism",
    "D2N": "Driver's seat backrest, release mechanism",
    "D2W": "Armrests on both sides, co-driver's seat",
    "D2Y": "Seat belt monitor",
    "D3B": "Luxury bed, bottom",
    "D3E": "Stowage facility, padded",
    "D3I": "Bunk, bottom",
    "D3K": "Seat cover, Dinamica, black, driver's seat",
    "D3L": "Seat cover, Dinamica, black, co-driver's seat",
    "D3R": "Seat cover, leather, co-driver's seat",
    "D3S": "Seat cover, leather, driver's seat",
    "D4J": "Mattress, ExtraPremiumComfort, bottom",
    "D4Q": "Shaving mirror",
    "D4S": "Roller sunblind, 1-piece, electric, windscreen",
    "D4U": "Curtain, for rear wall window",
    "D4Y": "Sunblind, side, driver's side",
    "D4Z": "Sunblind, side, driver's and co-driver's side",
    "D5F": "LED ambient lighting, driving and living",
    "D5O": "StyleLine",
    "D5R": "TrendLine",
    "D5S": "Seat cover, prem. flat-weave fabric, driver's seat",
    "D5T": "Seat cover, prem. flat-weave fabr., passenger seat",
    "D5V": "Flooring, weight-optimised",
    "D5Y": "Rubber mats, driver's and co-driver's side",
    "D5Z": "Carpet, engine tunnel",
    "D6C": "Auxiliary air conditioning, electric",
    "D6F": "Air conditioning system",
    "D6G": "Automatic climate control",
    "D6I": "Residual engine heat utilisation",
    "D6M": "Auxiliary hot water heater, cab",
    "D6V": "Noise and heat insulation of cab",
    "D6Z": "Construction-site filter",
    "D7A": "Heat insulation, additional",
    "D7F": "Stowage flaps, above windscreen, one lockable",
    "D7G": "Stowage compartment lid, driver and co-driver side",
    "D7I": "Stowage trays for stowage compartments",
    "D7J": "Drawers, under bed",
    "D7K": "Drawer, under dash support",
    "D7R": "Stowage flaps, above windscreen",
    "D7V": "Table, on co-driver's side",
    "D8A": "Roof hatch/vent, roof",
    "D8M": "Sliding/tilting sunroof, electric, glass version",
    "D8X": "Seat base, low, 40 mm lower",
    "D9A": "Pre-installation luxury bed, top, wide",
    "DUP0": "Basetype",
    # E
    "E1B": "Batteries 2 x 12 V/170 Ah, low-maintenance",
    "E1M": "Alternator, 28 V/150 A",
    "E1N": "Alternator 28 V/100 A",
    "E1U": "Alternator, controlled 24-30 V/150 A",
    "E1W": "AGM-Batteries, 2 x 12 V/170 Ah, maintenance-free",
    "E1Z": "AGM-Batteries, 2 x 12 V/220 Ah, maintenance-free",
    "E2J": "Automatic cutouts",
    "E3E": "Additional socket, 12 V/15 A, co-driver footwell",
    "E3L": "Socket, 24 V/15 A, co-driver footwell",
    "E3W": "PSM, 2nd generation",
    "E4C": "Additional functions, for body manufacturer",
    "E4D": "Body interface, behind cab",
    "E5A": "No. 1 switch, for non-MB body electrics",
    "E5B": "No. 2 switch, for non-MB body electrics",
    "E5C": "No. 3 switch, for non-MB body electrics",
    "E5K": "MirrorCam switch, on bed",
    "E6Z": "Reversing buzzer",
    "E7F": "Cable remote control for air suspension",
    "E8D": "USB-C connector, in side wall stowage comp., left",
    "E8E": "USB-C connector, in side wall stowage comp., right",
    "E9H": "Provision for fitting loading tailgate control",
    # F
    "F0F": "Side module, N3 vehicle",
    "F0G": "Side module, N3G vehicle",
    "F0T": "Mercedes star, illuminated from behind",
    "F0Y": "Mirror cover, construction vehicle",
    "F1B": "M-cab ClassicSpace, 2.30 m, tunnel 170 mm",
    "F1D": "L-cab ClassicSpace, 2.30 m, tunnel 170 mm",
    "F1I": "L-cab StreamSpace, 2.50 m, level floor",
    "F1Q": "M-cab",
    "F1R": "L-cab",
    "F2A": "Floor variant, flat floor",
    "F2B": "Floor variant, tunnel 170 mm",
    "F2E": "Floor variant tunnel 170 mm, for stowage compart. left",
    "F2G": "Cab width 2.30 m",
    "F2H": "Cab width 2.50 m",
    "F2N": "Cab, 600 mm attachment height",
    "F2P": "Cab, 765 mm attachment height",
    "F2U": "ClassicSpace",
    "F2W": "StreamSpace",
    "F3B": "Cab mountings, comfort, steel-sprung",
    "F3C": "Cab mountings, comfort, air-sprung",
    "F3Y": "Cab tilting mechanism, electrohydraulic",
    "F4H": "Cab rear wall, without window",
    "F4I": "Cab rear wall, with window",
    "F4X": "Stowage compartment exterior flap, left",
    "F4Y": "Stowage compartment exterior flap, right",
    "F4Z": "Stowage locker, left, under cab",
    "F5L": "Sun visor, exterior, transparent",
    "F5Y": "A-pillar trim",
    "F6D": "Windscreen, tinted, with filter band",
    "F6I": "Front mirror, heated",
    "F6Q": "Air horn",
    "F6R": "Air horns, cab roof",
    "F6T": "MirrorCam",
    "F6V": "MirrorCam bracket, chrome, lower cover, cab colour",
    "F7B": "Bumper, with steel corners",
    "F7C": "Bumper centre section with towing eyes",
    "F7D": "Bumper centre section w. towing eyes, coupling jaw",
    "F7T": "Door extension",
    "F7X": "Cab entrance, left/right, rigid",
    "F7Y": "Cab entrance, left/right, movable",
    "F8B": "2 remote control keys",
    "F8E": "Locking system, with central locking",
    "F8F": "Extended central locking",
    "F8V": "Light sensor",
    "F8W": "Rain sensor",
    # G
    "G0A": "Powertrain, 44 t to 68 t",
    "G0K": "Drive program, economy/power",
    "G0R": "Transmission support arms, optimised for removal",
    "G2E": "Transmission G 281-12/14.93-1.0",
    "G2F": "Transmission G 330-12/11.63-0.77",
    "G5A": "Single-disc clutch",
    "G5B": "Double-disc clutch",
    "G5G": "Mercedes PowerShift 3",
    "G5L": "PowerShift Advanced",
    # J
    "J1Z": "Speedometer, deletion, tachograph",
    "J2I": "Standard loudspeaker",
    "J2K": "Speaker, 2-way system",
    "J3Z": "Axle load measuring device",
    "J4X": "Belt warning w/ seat occup. detection, co-driver",
    "J5P": "Wireless charger for mobile phones",
    "J6E": "Multimedia Cockpit Interactive 2",
    "J7A": "Truck Data Center 8",
    "J7C": "Card Reader for Truck Data Center",
    "J8C": "Pre-fitted Card Reader for Truck Data Center",
    "J8U": "Pre-installation for Truck Data Center 8",
    "J9A": "Pre-installation for CB radio, 12 V, DIN slot",
    # K
    "K0T": "Main tank, left",
    "K1C": "Tank, 290 l, left, 650 x 565 x 950 mm, aluminium",
    "K1E": "Tank, 390 l, left, 650 x 565 x 1250 mm, aluminium",
    "K1Y": "Tank 330 l, left, 735 x 565 x 950 mm, aluminium",
    "K3T": "AdBlue tank, 25 l",
    "K3V": "AdBlue tank, 60 l, left",
    "K5M": "Tanks, lockable",
    "K5Q": "Fuel screen, tank filler neck",
    "K5R": "Protective plate for tank",
    "K5S": "Protective cap for AdBlue metering system",
    "K5Y": "Initial filling, additional 30 litres of fuel",
    "K7N": "Exhaust system, outlet to left, under 30 degrees",
    "K7R": "Exhaust pipe, straight, above second axle",
    "K7S": "Exhaust pipe, curved, above second axle",
    # L
    "L0A": "Illumination regulation, in acc. with UN-R 48.06",
    "L0Y": "Tail lamps wiring harness, extended",
    "L1C": "LED daytime running lamps",
    "L1D": "Automatic main/dipped beam and cornering light",
    "L1G": "LED main headlamps",
    "L1M": "LED fog lamps",
    "L1P": "LED tail lights",
    "L1Q": "Tail lights, construc. in metal holder with grille",
    "L1W": "LED turn signals in light signature",
    "L2H": "Side marker lamps, flashing",
    "L9D": "Pre-installation for additional indicator lights",
    # M
    "M0A": "Engine mounts, reinforced",
    "M0C": "Bottom shell to prevent swirling-up of dust",
    "M0Q": "Noise regulation acc. to UN-R 51.03, phase 2",
    "M0U": "Noise encapsulation, special package",
    "M3D": "Eng. OM471, inline 6, 12.8 l, 375kW (510hp), 2500 Nm",
    "M3E": "Eng. OM471, inline 6, 12.8 l, 390kW (530hp), 2600 Nm",
    "M4X": "Engine version Euro VI, E",
    "M5B": "2. Engine generation OM471",
    "M5D": "3. Engine generation OM471",
    "M5U": "Exhaust brake, standard system",
    "M5V": "High Performance Engine Brake",
    "M6L": "Air compressor, 2-cylinder",
    "M6M": "Air compressor, 2-stage, for optimised consumption",
    "M7I": "Insect screen in front of cooling system",
    "M7T": "Water pump, governed",
    "M7U": "Cooling output for hot regions",
    "M8A": "Air intake from front",
    "M8B": "Air intake behind cab, mounted",
    "M8D": "Air intake, above corner, integrated in cab",
    "M8Y": "Fuel pre-filter, chassis-mounted, additional",
    "M9V": "Deletion, guard plate, bumper",
    # N
    "N1G": "PTO MB, 123-10b, flange, low-speed",
    "N2E": "PTO MB 131-2c, pump",
    "N6P": "Provision for PTO, via external transfer case",
    "N6Z": "Transmission oil cooling",
    # O
    "O3C": "Safety Package",
    "O3D": "Safety Package, without roll control",
    "O3J": "Climate Package, with noise/heat insulation",
    "O3K": "Active Safety",
    "O8K": "Driving Package",
    "OWY": "Interior measures upgrade",
    "OYL": "Storage Package",
    "OYN": "Sight Package, with LED main headlamps",
    "OYP": "Comfort Package, with ExtraPremiumComfort mattress",
    "OYR": "Active safety pack Overseas plus",
    "OYW": "Grounder version",
    # P
    "P0S": "Space for control unit betw. driv. seat & door pocket",
    "P9A": "Tip control, in cab",
    "P9K": "Pre-installation, rear-end tipper, Korea",
    # Q
    "Q0Q": "Front spring, 2 x 10.0 t, 4-leaf",
    "Q1X": "Front spring, 2 x 8.0 t, 3-leaf",
    "Q1Y": "Front spring, 9.0 t, 4-leaf",
    "Q3A": "Rear spring, 2 x 13.0 t",
    "Q3B": "Rear springs, 2 x 13.0 t, for axle spacing 1450 mm",
    "Q8N": "End crossmember, 300 mm indented",
    # R
    "R2F": "Light-alloy wheels, 8.25 x 22.5, Speedline",
    "R2K": "Light-alloy wheels, 9.00 x 22.5, Speedline",
    "R2U": "Aluminium rims 11.75 x 22.5, front axle, Speedline",
    "R6M": "Aluminium whls, 11.75 x 22.5, FA, Speedline, ET135",
    # S
    "S1D": "Stability Control Assist (ESP)",
    "S1H": "Lane Keeping Assist",
    "S1I": "Proximity Control Assist",
    "S1L": "Attention Assist",
    "S2D": "Active Brake Assist 6",
    "S2H": "Active Sideguard Assist 2",
    "S2L": "Frontguard Assist",
    "S2N": "Active Brake Assist 6 Plus",
    "S2Q": "Sensor position, side radar, widened",
    "S3A": "Airbag, driver",
    "S5A": "Speed limiter, 90 km/h (56 mph), ECE",
    "S5Z": "Cruise control",
    "S8C": "Hazard warning triangle",
    "S8D": "Warning lamp",
    # T
    "T6D": "Weight variant 41.0 t (10.0/10.0/10.5/10.5)",
    # U
    "U2G": "Exhaust box",
    "U3S": "3rd-generation electronics architecture",
    # V
    "V0R": "No check for N3G conformity",
    "V0T": "Vehicle class N3G, off-road vehicle",
    "V0U": "Overhang angle, front, minimum 25 degrees",
    "V0W": "Breakover angle, minimum 25 degrees",
    "V0X": "Ground clearance under front axle, minimum 250 mm",
    "V0Y": "Ground clearance under rear axle, minimum 250 mm",
    "V0Z": "Ground clearance between axles, minimum 300 mm",
    "V1B": "Arocs",
    "V1W": "Standard",
    "V1Z": "Grounder",
    "V2J": "Arocs model generation 5",
    "V8B": "Chassis number FIN with model year",
    "V8W": "Model year 6",
    "V8X": "Model year 7",
    "V9F": "Technical changes model year April",
    "V9G": "Technical changes model year October",
    # W
    "W4J": "Weight variant 28.0 t (9.0/10.0/10.0)",
    "W5Y": "Weight variant 33.0 t (9.0/13.0/13.0)",
    "W7G": "Weight variant 37.0 t (8.0/8.0/13.0/13.0)",
    # X
    "X2A": "Model identification, acc. to weight variant",
    "X2I": "Model plate, export",
    "X2V": "Inner/outer turning circle not as per ECE dir.",
    "X3W": "Powertrain warranty as per T and Cs 3yrs/450,000km",
    "X3Z": "Powertrain warranty as per T and Cs 3yrs/250,000km",
    "X4B": "Instrument/labels/documentation, Korean",
    # Y
    "Y1W": "Refrigerator, on engine tunnel",
    "Y1X": "Pull-out refrigerator, under bed",
    "Y3L": "Preservation for transport",
    "Y4A": "Telescopic jack, 12 t/19 t",
    "Y4H": "Holder for wheel chock",
    "Y4I": "1 wheel chock",
    "Y4J": "2 wheel chocks",
    "Y4Z": "Compressed-air gun, with hose",
    "Y6A": "Country-specific version",
    # Z
    "Z4O": "Tank cross-section, narrow",
    "Z4P": "Tank cross-section, wide",
    "Z4Q": "Tank cross-section, low",
    "Z5E": "OM 471",
    "Z5M": "PTO, single",
    "Z5S": "Power take-off, pump, under top edge of frame",
    "Z5U": "Power take-off, propshaft, under top edge of frame",
    "Z5X": "Left-hand drive",
    "Z5Y": "Vehicle, for right-side traffic",
    # A (additional)
    "A0B": "Axle, wheel mounting track, narrow",
    "A1A": "Front axle with air suspension",
    "A2I": "Rear axle, crown wheel 485, hypoid, 13.0 t",
    "A3D": "Rear axle with active lubrication, uncontrolled",
    "A4K": "Trail. axle 10 t, de-loadable, liftable, twin tyres",
    "A5B": "Axle ratio i = 2.533",
    # B (additional)
    "B5I": "Brake and electrical connections, high",
    # C (additional)
    "C0A": "Frame overhang 750 mm",
    "C1J": "Wheelbase 3250 mm",
    "C5B": "Step plate above frame, partial cover",
    "C5D": "Step, behind cab, left",
    "C6G": "Steering, Servotwin",
    "C8B": "Rear wing, 2550 mm vehicle width",
    "C8H": "Wing, 3-piece, with EC splash guard",
    "CSJ": "Underbody panelling, ProCabin, standard",
    "CZE": "Front mudguard, fender skirt, aerodynamically optimised",
    # D (additional)
    "D1Q": "Co-driver's suspension seat, ventilated",
    "D2J": "Seat version, Korea",
    "D4E": "Mattress topper for lower comfort bed",
    "D5E": "LED ambient lighting",
    "D5K": "2 LED reading lamps, gooseneck",
    "D7N": "Flexible shelving sys., f. stowage above windscreen",
    # E (additional)
    "E0D": "Battery sensor, Hella",
    "E0Q": "Batteries from company Enersys",
    "E1T": "Alternator, controlled 24-30 V/100 A",
    "E4W": "Starting-off aid, speed limit 30 km/h",
    "E6A": "Trailer socket, 24 V, 15-pin",
    "E6E": "Adapter, 15-pin to 2x7-pin socket",
    # F (additional)
    "FAV": "Cab version ProCabin",
    "FZY": "Vehicle width, 2500 mm",
    "F2V": "BigSpace",
    "F3P": "ProCabin-Stream, level floor",
    "F3Q": "ProCabin-Big, level floor",
    "F4T": "Top entrance, painted",
    "F4V": "A-pillar cladding, aerodynamically optimised",
    "F5B": "Air deflector, snap-in, with cab side deflectors",
    "F5K": "Air deflectors, loose",
    "F6E": "Windscreen, tinted, with filter band, heated",
    "F7A": "Bumper, with plastic corners",
    # G (additional)
    "G0T": "Predictive Powertrain Control",
    # H
    "H2J": "Fifth-wheel lead +950 mm",
    # I — vehicle classification / production codes
    "I4D": "Wheel arrangement 6x2, trailing axle, twin tyres",
    "I4L": "Wheel arrangement 8x4/4",
    "I5F": "26.0-tonner",
    "I5G": "32.0-tonner",
    "I4I": "Wheel arrangement 6x4",
    "I6A": "Rigid chassis",
    "I6B": "Tipper chassis",
    "I6D": "Semitrailer tractor",
    "I6I": "Vehicle production plant Wörth",
    "I6K": "Heavy-duty model series, new generation from 18 t",
    "I6M": "Heavy-duty vehicles from 18 t, off-road",
    "I6N": "Heavy-duty vehicles from 18 t, on-road",
    "I6W": "Leaf suspension, rear axle",
    "I6X": "Air suspension, rear axle",
    # J (additional)
    "J2J": "Sound system",
    "J7G": "GPRS1 Config Fragment G_SIM ModemEU",
    "J7Q": "Driving assistance map, South Korea region",
    # K (additional)
    "K0W": "Second tank, right",
    "K1I": "Tank, 290 l, left, 650 x 700 x 750 mm, aluminium",
    "K6G": "Second tank, 220 l, right, 650 x 700 x 600 mm, aluminium",
    # L (additional)
    "L2G": "LED side turn signal lamps",
    "L3K": "1 LED work light, cab rear wall, top",
    "L6A": "Intelligent Light",
    # M (additional)
    "M4Y": "Certification according to ECE",
    "M6R": "Air compressor, two-stage, deactivatable",
    # O (additional)
    "OKS": "Cooling module, standard",
    "O0A": "Coolant service interval, long for non-SWR",
    "O1S": "Interior colour almond beige",
    "O1T": "Interior colour greige/anthracite",
    "O1Z": "Steering, indirect",
    "O2N": "Starter Melco 95P65",
    "O3R": "Actros L",
    "O5J": "Country-spec. contr. code FIN/VIN-corr. divergent",
    "O5Q": "Control code for A dimension, rear axle 435 mm",
    # Q (additional)
    "Q0W": "Fifth-wheel coupling ex factory",
    "Q3Z": "Lowered frame, with residual bellow pressure ctrl.",
    "Q4K": "Fifth wheel coupling height = 185 mm",
    "Q4X": "Fifth wheel coupling, manually lubricated",
    "Q5Q": "Fifth wheel coupling, standard, Jost JSK 37C",
    "Q5Y": "Drive-on ramp/coupling aid",
    "Q6D": "Mounting plate, 40 mm, 20 t",
    "Q6W": "5th-wheel bracket, w/ hole pattern, raised, H=50mm",
    # R (additional)
    "R2J": "Light-alloy wheels, 9.00x22.5, matt, Alcoa",
    "R2Y": "Alum. wheels 9.00 x 22.5, Dura-Bright, Alcoa",
    # S (additional)
    "S2E": "Active Drive Assist 3",
    # U (additional)
    "U1W": "AdBlue lines, water-heated",
    "U2K": "Control code, high PTO transmission oil level",
    "U2S": "Control code, exhaust box, left-hand outlet",
    "U2V": "Control code, catalytic converter kit 2",
    "U3D": "Control code, CAN star points, classic",
    "U3F": "Control code, global AdBlue sensor (GMS DEF)",
    "U3H": "Control code, Tachometer Simulator Unit (TSU)",
    "U3I": "Control code, NFD standard",
    "U4U": "Control code, tail light bracket POS 3 HUF, 12 mm",
    # V (additional)
    "V0S": "Vehicle class N3",
    "V1A": "Actros",
    "V2B": "Actros model generation 5",
    # W (additional)
    "W4E": "Weight variant 28.0 t (8.0/10.0/10.0)",
    # Z (additional)
    "Z3Z": "Export code",
    "Z4R": "Tank cross-section, high",
    "Z5P": "Clutch supplier F&S",
    "Z5Q": "Clutch supplier LUK",
    "Z8P": "CTT vehicle, conversion on assembly line",
    "Z8U": "CTT vehicle",
    "Z9A": "Constructability request order, special control",
    # Special J-prefix codes (internal / option codes starting with J)
    "JC9B": "Frame overhang 3300 mm",
    "JCAL": "Extension of wheelbase (JCAL)",
    "JCKD": "Battery carrier relocated to dimension 3625 mm",
    "JCRP": "Reinforcement, plate crossmembers, rear axles",
    "JCUX": "Extension of wheelbase (JCUX)",
    "JCWV": "Wheelbase 5900 mm",
    "JCWW": "Extension of wheelbase (JCWW)",
    "JCXX": "Extension of wheelbase",
    "JF3C": "Cab mountings, comfort, air-sprung",
    "JK0U": "Main tank, right",
    "JK3V": "AdBlue tank, 60 l, left",
    "JK4E": "Tank, 390 l, right, 650 x 565 x 1250 mm, aluminium",
    "JK5Y": "Initial filling, additional 30 litres of fuel",
    "JK6H": "JK6H option",
    "JKUR": "AdBlue-Tank relocated to the right",
    "JKVY": "Tank moved to measure 3125 mm",
    "JR6M": "Aluminium whls, 11.75 x 22.5, FA, Speedline, ET135",
    "JQYY": "Vehicle operation without trailer",
    "JW7Y": "Weight variant 41.0 t (8.0/8.0/13.0/13.0)",
    "JZYI": "Control code, no EU/ECE conformity",
    "JZYN": "Control code, no CoC, national individual regist",
    "JZYU": "Control code, system approvals list not complete",
}


def _lookup_code(code: str) -> str:
    """Return description for a code, stripping leading J for special codes."""
    code = code.strip()
    if code in OPTION_CODE_MAP:
        return OPTION_CODE_MAP[code]
    # Try without leading J (e.g. JF3C -> F3C)
    if code.startswith("J") and len(code) > 1:
        stripped = code[1:]
        if stripped in OPTION_CODE_MAP:
            return OPTION_CODE_MAP[stripped] + " (J-variant)"
    return "설명 없음"


@st.dialog("옵션 코드 상세 설명", width="large")
def show_code_details(commission_no: str, sam_str: str, wings_str: str):
    st.markdown(f"**Commission No.:** `{commission_no}`")
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### SAM에만 있는 코드")
        sam_codes = [c.strip() for c in str(sam_str).split(",") if c.strip() and c.strip() != "nan"]
        if sam_codes:
            for code in sam_codes:
                desc = _lookup_code(code)
                st.markdown(f"**`{code}`** &nbsp; {desc}")
        else:
            st.info("없음")

    with col2:
        st.markdown("#### WINGS에만 있는 코드")
        wings_codes = [c.strip() for c in str(wings_str).split(",") if c.strip() and c.strip() != "nan"]
        if wings_codes:
            for code in wings_codes:
                desc = _lookup_code(code)
                st.markdown(f"**`{code}`** &nbsp; {desc}")
        else:
            st.info("없음")



def parse_wings(file) -> pd.DataFrame:
    # supports uploaded CSV or Excel bytes
    try:
        df = pd.read_csv(file, encoding='utf-8')
    except Exception:
        file.seek(0)
        df = pd.read_excel(file)

    # normalize column names
    cols = {c: c.strip() for c in df.columns}
    df.rename(columns=cols, inplace=True)

    # expected columns in sample: 'Commission no.' and code columns
    if 'Commission no.' not in df.columns:
        st.error('CSV/Excel에서 `Commission no.` 컬럼을 찾을 수 없습니다.')
        return pd.DataFrame()

    # Find model name column: prefer 'Type (brief)', fallback to 'Type', or 'Baumuster'
    model_col = None
    for col_name in df.columns:
        if 'type' in col_name.lower() and 'brief' in col_name.lower():
            model_col = col_name
            break
    if not model_col:
        for col_name in df.columns:
            if col_name.lower() == 'type':
                model_col = col_name
                break
    if not model_col:
        model_col = 'Baumuster' if 'Baumuster' in df.columns else None

    if model_col is None:
        st.warning('모델명 컬럼을 찾을 수 없습니다. Baumuster 컬럼이 모델명으로 사용됩니다.')
        model_col = df.columns[1] if len(df.columns) > 1 else 'Commission no.'

    # Prefer explicit option code columns from WINGS export
    wings_opt_col1 = None
    wings_opt_col2 = None
    
    for col_name in df.columns:
        if 'Standard' in col_name and 'equipment' in col_name:
            wings_opt_col1 = col_name
        elif 'Additional' in col_name and 'equipment' in col_name:
            wings_opt_col2 = col_name
    
    # If explicit columns not found, try alternative names
    if not wings_opt_col1 or not wings_opt_col2:
        code_cols = []
        try:
            if df.shape[1] >= 11:
                # 0-based: I -> 8, K -> 10
                code_cols = [df.columns[8], df.columns[10]]
        except Exception:
            pass
        
        if code_cols:
            wings_opt_col1, wings_opt_col2 = code_cols[0], code_cols[1]
    
    # Fallback if still no columns found
    if not wings_opt_col1:
        for name in df.columns:
            low = name.lower()
            if 'equipment' in low or 'offer code' in low or 'enumeration' in low:
                if wings_opt_col1 is None:
                    wings_opt_col1 = name
                elif wings_opt_col2 is None:
                    wings_opt_col2 = name
                    break

    def extract_codes(text):
        if pd.isna(text):
            return set()
        text = str(text)
        # Find 3-4 char tokens but require at least one digit (filter out words like WITH, NOT)
        raw_tokens = re.findall(r"[A-Z0-9]{3,4}", text.upper())
        return set(t for t in raw_tokens if any(ch.isdigit() for ch in t))

    # Extract codes from specified columns
    code_cols_to_use = []
    if wings_opt_col1:
        code_cols_to_use.append(wings_opt_col1)
    if wings_opt_col2:
        code_cols_to_use.append(wings_opt_col2)
    
    if code_cols_to_use:
        df['WINGS_codes'] = df[code_cols_to_use].astype(str).agg(' '.join, axis=1).apply(extract_codes)
    else:
        # Final fallback
        df['WINGS_codes'] = df.astype(str).agg(' '.join, axis=1).apply(extract_codes)
    
    # Return with both Model name and Baumuster number, plus additional columns
    result_cols = ['Commission no.', model_col, 'WINGS_codes']
    if 'Baumuster' in df.columns and model_col != 'Baumuster':
        result_cols.insert(2, 'Baumuster')
    
    # Add additional WINGS columns if they exist
    additional_cols = [
        'Order status financial', 'Order status logistical',
        'Additional equipment (enumeration)', 'FIN', 'Subcategory (ID)',
        'Vehicle alterable until', 'Requested delivery date'
    ]
    for col in additional_cols:
        if col in df.columns:
            result_cols.append(col)
    
    result = df[result_cols].copy()
    result.rename(columns={model_col: 'Model'}, inplace=True)
    return result


def _normalize_model(model: str) -> str:
    """Normalize model name: remove spaces/DNA, apply historic mappings, convert 28xx->26xx"""
    if not isinstance(model, str):
        return ''
    # Remove all non-alphanumeric, convert to uppercase, remove DNA
    cleaned = re.sub(r'[^A-Z0-9]', '', model.upper().replace('DNA', '').strip())
    
    # Apply historic mappings (4153->3253, etc)
    historic = {
        '4153': '3253',
        '2851': '2651',
        '2135': '1835',
        '2863': '2663',
        '2853': '2653',
    }
    for old, new in historic.items():
        if cleaned.startswith(old):
            cleaned = new + cleaned[len(old):]
            break
    
    # Convert 28xx -> 26xx pattern
    if cleaned.startswith('28'):
        cleaned = '26' + cleaned[2:]
    
    return cleaned


def _extract_variant_tokens(text: str, codes: set) -> set:
    tokens = set()
    if not text:
        text = ''
    t = text.upper()
    # detect S-pattern like S5F
    for m in re.findall(r"\bS\d[A-Z0-9]?\b", t):
        tokens.add(m)
    # detect axle patterns like 8x4, 6x4
    for m in re.findall(r"\b\dX\d\b", t):
        tokens.add(m)
    # also check codes set
    for c in codes:
        uc = c.upper()
        if re.match(r"^S\d[A-Z0-9]?$", uc) or re.match(r"^\dX\d$", uc):
            tokens.add(uc)
    return tokens


def parse_sam_docx(uploaded_files) -> dict:
    """Parse SAM .docx files using XML extraction; return {normalized_model: set(codes)}"""
    mapping = {}
    
    for up in uploaded_files:
        name = up.name
        model_raw = None
        codes = set()
        
        try:
            # Read .docx as zip and extract XML
            if name.lower().endswith('.docx'):
                with zipfile.ZipFile(up) as z:
                    xml_content = z.read('word/document.xml')
                root = ET.fromstring(xml_content)
                
                # Extract all text from XML
                full_text = "".join(
                    t.text for t in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                    if t.text
                )
                
                # Extract option codes AFTER "Standard equipment" section only
                if 'Standard equipment' in full_text:
                    codes_text = full_text.split('Standard equipment')[-1]
                else:
                    codes_text = full_text
                
                # Extract 3-4 char codes but filter out pure alphabetic (like WITH, NOT)
                # Option codes must contain at least one digit
                raw_codes = re.findall(r'\b[A-Z0-9]{3,4}\b', codes_text.upper())
                codes = set(c for c in raw_codes if any(ch.isdigit() for ch in c))
                
                # Try to extract model from XML text (Vehicle type, Type, Model, Baumuster)
                for pattern in [
                    r'Vehicle type[:\s]+([0-9]{4}[A-Z]{1,3})',
                    r'Type[:\s]+([0-9]{4}[A-Z]{1,3})',
                    r'Model[:\s]+([0-9]{4}[A-Z]{1,3})',
                    r'Baumuster[:\s]+([0-9]{4}[A-Z]{1,3})'
                ]:
                    m = re.search(pattern, full_text, re.IGNORECASE)
                    if m:
                        model_raw = m.group(1).strip()
                        break
            else:
                # CSV or TXT files
                try:
                    text = up.getvalue().decode('utf-8')
                except Exception:
                    text = str(up.getvalue())
                
                # Extract 3-4 char codes but require at least one digit
                raw_codes = re.findall(r'\b[A-Z0-9]{3,4}\b', text.upper())
                codes = set(c for c in raw_codes if any(ch.isdigit() for ch in c))
        
        except Exception as e:
            st.warning(f'SAM 파일 읽기 오류 ({name}): {str(e)[:50]}')
            continue
        
        # If model not found in XML, extract from filename
        if not model_raw:
            # Pattern: extract 4-digit+letters from filename (e.g., "3353S", "2851LS")
            fname_upper = name.upper()
            m = re.search(r'(\d{4}[A-Z]{1,3}(?:[LSK])?)', fname_upper)
            if m:
                model_raw = m.group(1)
        
        # Normalize and store
        if model_raw and codes:
            model_norm = _normalize_model(model_raw)
            if model_norm:
                if model_norm not in mapping:
                    mapping[model_norm] = set()
                mapping[model_norm].update(codes)
                st.write(f"✓ SAM 파일 '{name}' → 모델 '{model_norm}' ({len(codes)} 코드)")
    
    return mapping


def compare(df_wings: pd.DataFrame, sam_map: dict) -> pd.DataFrame:
    rows = []
    for _, r in df_wings.iterrows():
        com = r['Commission no.']
        # Handle both 'Model' (new format) and 'Baumuster' (legacy format)
        model_raw = r.get('Model') or r.get('Baumuster', '')
        baumuster_num = r.get('Baumuster', '') if 'Model' in r else ''
        wings_codes = set(r['WINGS_codes'] or [])
        model_norm = _normalize_model(model_raw)

        # Look up SAM codes using normalized model
        sam_codes = sam_map.get(model_norm, set())

        # If no exact match, try relaxed matching: numeric prefix must match AND letter suffix must match
        if not sam_codes:
            def _split_model(s: str):
                # split into leading digits and trailing letters e.g. '3253K' -> ('3253', 'K')
                m = re.match(r'^(\d+)([A-Z]*)$', s)
                if m:
                    return m.group(1), m.group(2)
                return s, ''

            num_norm, suf_norm = _split_model(model_norm)
            for k, v in sam_map.items():
                try:
                    k_norm = _normalize_model(k)
                except Exception:
                    k_norm = _normalize_model(str(k))
                num_k, suf_k = _split_model(k_norm)
                # numeric prefixes must match AND suffixes must match (both empty counts as match)
                if k_norm == model_norm or (num_k == num_norm and suf_k == suf_norm):
                    sam_codes = v
                    break

        only_w = sorted(wings_codes - sam_codes) if sam_codes else []
        only_s = sorted(sam_codes - wings_codes)

        # Place important columns in desired order. Put Model_norm first, then
        # Changeability Date (renamed from 'Vehicle alterable until'), then Until Dealine,
        # and prefer Only_in_SAM before Only_in_WINGS.
        # Start with explicit copies from the WINGS row to avoid accidental blanks
        row_dict = {
            'Commission no.': com,
            'Baumuster': r.get('Baumuster', '') if 'Baumuster' in r.index else baumuster_num,
            'Model': r.get('Model', model_raw) if 'Model' in r.index else model_raw,
            'Model_norm': _normalize_model(r.get('Model') or r.get('Baumuster') or model_raw),
            'Changeability Date': '',
            'Until Dealine': '',
            'Only_in_SAM': ','.join(only_s),
            'Only_in_WINGS': ','.join(only_w) if sam_codes else '',
        }
        
        # compute days until deadline (Vehicle alterable until)
        # Process Changeability Date display and Until Dealine together.
        change_raw = r.get('Vehicle alterable until', '')
        change_display = ''
        days_left = ''
        if change_raw:
            try:
                cdt = pd.to_datetime(change_raw, errors='coerce')
                if not pd.isna(cdt):
                    # If date is in the past, mark Passed for both display and deadline
                    if cdt.date() < date.today():
                        change_display = 'Passed'
                        days_left = 'Passed'
                    else:
                        change_display = cdt.strftime('%Y-%m-%d')
                        days_left = (cdt.date() - date.today()).days
                else:
                    s = str(change_raw).strip()
                    if s:
                        if s.lower() in ('done', 'passed'):
                            change_display = 'Passed'
                            days_left = 'Passed'
                        else:
                            change_display = s
                            days_left = ''
            except Exception:
                s = str(change_raw).strip()
                change_display = 'Passed' if s.lower() in ('done', 'passed') else s
                days_left = 'Passed' if s.lower() in ('done', 'passed') else ''

        row_dict['Changeability Date'] = change_display
        row_dict['Until Dealine'] = days_left
        # Add additional WINGS columns if they exist in df_wings, excluding
        # 'Vehicle alterable until' because we've already exposed it as
        # 'Changeability Date'. Also exclude gross price column per request.
        additional_cols = [
            'Order status financial', 'Order status logistical',
            'Additional equipment (enumeration)', 'FIN', 'Subcategory (ID)',
            'Requested delivery date'
        ]
        for col in additional_cols:
            if col in r.index:
                row_dict[col] = r[col]

        rows.append(row_dict)
    return pd.DataFrame(rows)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
        # Select key columns for output in desired order
        output_cols = ['Commission no.', 'Baumuster', 'Model', 'Model_norm', 'Changeability Date',
                       'Until Dealine', 'Only_in_SAM', 'Only_in_WINGS',
                       'Order status financial', 'Order status logistical', 'Gross equipment price (repricing)',
                       'Additional equipment (enumeration)', 'FIN', 'Subcategory (ID)',
                       'Requested delivery date']
        available_cols = [c for c in output_cols if c in df.columns]
        df[available_cols].to_excel(writer, index=False, sheet_name='comparison')
    return towrite.getvalue()


def main():
    st.set_page_config(page_title='WINGS vs SAM 비교', layout='wide')

    # --- Dashboard (existing code below) ---
    # 앱 배경 및 로고 처리: workspace의 assets/ 아래 파일이 있으면 사용,
    # 없으면 업로드 위젯으로 업로드하도록 합니다.
    assets_dir = Path('assets')
    assets_dir.mkdir(exist_ok=True)

    def _b64_from_bytes(b: bytes) -> str:
        return base64.b64encode(b).decode('ascii')

    def _set_background_from_path(p: Path):
        try:
            b = p.read_bytes()
            b64 = _b64_from_bytes(b)
            mime = 'image/png' if p.suffix.lower() == '.png' else 'image/jpeg'
            # Create a background that fades to white toward the edges so
            # the image blends with Streamlit's white page background.
            # We place a transparent-to-white radial-gradient on top of the
            # image so the edges become white while the center stays visible.
            css = f"""
            <style>
            .stApp {{
                background-image: url('data:{mime};base64,{b64}');
                background-size: cover;
                background-position: center top;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            /* semi-transparent white overlay on the entire app */
            .stApp::before {{
                content: '';
                position: fixed;
                inset: 0;
                background: rgba(255, 255, 255, 0.82);
                z-index: 0;
                pointer-events: none;
            }}
            /* keep all content above the overlay */
            .stApp > * {{
                position: relative;
                z-index: 1;
            }}
            </style>
            """
            st.markdown(css, unsafe_allow_html=True)
        except Exception:
            pass

    def _set_logo_from_path(p: Path):
        try:
            b = p.read_bytes()
            b64 = _b64_from_bytes(b)
            mime = 'image/png' if p.suffix.lower() == '.png' else 'image/jpeg'
            # place a small, sharp logo centered above the title
            html = f"""
            <div style="position:fixed;left:50%;top:8px;transform:translateX(-50%);z-index:9999;">
                <img src='data:{mime};base64,{b64}' style='height:36px;opacity:1;border-radius:2px;display:block;'/>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
        except Exception:
            pass

    # Load existing images from assets but do not show selection/upload widgets
    img_files = [p for p in assets_dir.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg')]

    bg_path = None
    logo_path = None
    if img_files:
        # Prefer files with semantic names; otherwise use the first discovered file
        bg_path = next((p for p in img_files if 'background' in p.stem.lower() or 'truck' in p.stem.lower()), img_files[0])
        logo_path = next((p for p in img_files if 'logo' in p.stem.lower()), None)

    # Apply visuals if available (background first, then logo overlay)
    if bg_path and bg_path.exists():
        _set_background_from_path(bg_path)
    if logo_path and logo_path.exists():
        _set_logo_from_path(logo_path)

    st.title('WINGS ↔ SAM 옵션 코드 비교 대시보드')

    st.markdown('업로드: WINGS CSV/Excel 파일과 SAM `.docx` 또는 CSV 파일들을 업로드하세요.')

    wings_file = st.file_uploader('WINGS CSV/Excel 파일', type=['csv', 'xlsx', 'xls'])
    sam_files = st.file_uploader('SAM files (.docx/.csv) (여러개 가능)', type=['docx', 'csv', 'xlsx', 'txt'], accept_multiple_files=True)

    if st.button('샘플로 데모 실행'):
        # load embedded sample from attachments? Not available; show message
        st.info('샘플 데모를 사용하려면 실제 파일을 업로드하세요.')

    if wings_file is not None:
        df_w = parse_wings(wings_file)
        st.success(f'WINGS 파일 읽음: {len(df_w)} 행')

        sam_map = {}
        if sam_files:
            sam_map = parse_sam_docx(sam_files)
            st.success(f'SAM 파일 읽음: {len(sam_map)} 모델')

        comp = compare(df_w, sam_map)

        st.subheader('요약')
        st.metric('Commission 수', len(comp))
        # count rows without SAM match
        if 'SAM_matched' in comp.columns:
            missing = int((~comp['SAM_matched']).sum())
        else:
            missing = int(len(comp))
        st.metric('SAM 매핑 없음', missing)

        # ── Prepare data splits ──────────────────────────────────────────────
        cols_table = ['Commission no.', 'Baumuster', 'Until Dealine', 'Changeability Date',
                      'Model', 'Model_norm', 'Only_in_SAM', 'Only_in_WINGS']

        if 'Until Dealine' in comp.columns:
            comp['_UntilDealine_days'] = pd.to_numeric(comp['Until Dealine'], errors='coerce')
            very_urgent = comp[
                (comp['_UntilDealine_days'].notna()) &
                (comp['_UntilDealine_days'] >= 0) &
                (comp['_UntilDealine_days'] <= 14)
            ].copy().sort_values('_UntilDealine_days', ascending=True)
            urgent = comp[
                (comp['_UntilDealine_days'].notna()) &
                (comp['_UntilDealine_days'] >= 0) &
                (comp['_UntilDealine_days'] <= 60)
            ].copy().sort_values('_UntilDealine_days', ascending=True)
        else:
            very_urgent = pd.DataFrame()
            urgent = pd.DataFrame()

        # ── Section 1: Urgent Correction Needed (within 2 weeks) ─────────────
        st.markdown('<h2 style="color:red">🚨 Urgent Correction Needed (within 2 weeks)</h2>', unsafe_allow_html=True)
        if not very_urgent.empty:
            available = [c for c in cols_table if c in very_urgent.columns]
            very_urgent_display = very_urgent[available].reset_index(drop=True)
            st.caption("행을 클릭하면 해당 Commission의 옵션 코드 상세 설명이 표시됩니다.")
            vu_event = st.dataframe(
                very_urgent_display,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True,
            )
            if vu_event.selection.rows:
                uidx = vu_event.selection.rows[0]
                urow = very_urgent_display.iloc[uidx]
                show_code_details(
                    str(urow.get("Commission no.", "")),
                    str(urow.get("Only_in_SAM", "")),
                    str(urow.get("Only_in_WINGS", "")),
                )
            st.download_button(
                '📥 Urgent (2주 이내) Excel 다운로드',
                data=to_excel_bytes(very_urgent_display),
                file_name='urgent_2weeks.xlsx',
                key='dl_very_urgent',
            )
        else:
            st.success("2주 이내 긴급 수정 필요 건 없음")

        st.divider()

        # ── Section 2: Changeability within 60 days ──────────────────────────
        st.markdown('<h2 style="color:black">Changeability within 60 days</h2>', unsafe_allow_html=True)
        if not urgent.empty:
            available = [c for c in cols_table if c in urgent.columns]
            urgent_display = urgent[available].reset_index(drop=True)
            st.caption("행을 클릭하면 해당 Commission의 옵션 코드 상세 설명이 표시됩니다.")
            u_event = st.dataframe(
                urgent_display,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True,
                key="df_60days",
            )
            if u_event.selection.rows:
                uidx = u_event.selection.rows[0]
                urow = urgent_display.iloc[uidx]
                show_code_details(
                    str(urow.get("Commission no.", "")),
                    str(urow.get("Only_in_SAM", "")),
                    str(urow.get("Only_in_WINGS", "")),
                )
            st.download_button(
                '📥 Changeability (60일 이내) Excel 다운로드',
                data=to_excel_bytes(urgent_display),
                file_name='changeability_60days.xlsx',
                key='dl_urgent',
            )
        else:
            st.info("60일 이내 수정 필요 건 없음")

        st.divider()

        # ── Overall Excel download ────────────────────────────────────────────
        st.download_button(
            '📥 전체 데이터 Excel 다운로드',
            data=to_excel_bytes(comp),
            file_name='wings_sam_comparison_all.xlsx',
            key='dl_all',
        )


if __name__ == '__main__':
    main()

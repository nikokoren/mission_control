"""
Hand-written trivia bank, one pool per rocket family plus a general pool.

Kept in its own file purely because it is long and never changes.
The seed makes the choice stable: the same launch always gets the same
fact, so it does not flicker between refreshes and does not force a new
git commit every run.
"""

import random


def get_rocket_fact(rocket_name, seed=""):
    r_name = (rocket_name or "").lower()

    general_facts = [
        "Launch pad water deluge systems reduce the intense acoustic and pressure waves produced at liftoff, protecting the rocket and launch pad.",
        "A spacecraft in low Earth orbit travels at roughly 17,500 mph (28,000 km/h).",
        "The Kármán line, 100 km (62 miles) above Earth, is widely used as a conventional boundary of space.",
        "Rockets are mostly fuel; often over 85% of a launch vehicle's mass is propellant, leaving little room for payload.",
        "Max-Q is the point during ascent when a rocket experiences its highest dynamic pressure, caused by the combination of air density and speed.",
        "Most rockets use a 'Gravity Turn', tilting slightly after liftoff to let gravity do the work of turning the rocket horizontal.",
        "Hypergolic propellants ignite automatically when they come into contact, making them useful for spacecraft engines that need reliable starts and restarts.",
        "Pogo oscillation is a coupled vibration between a rocket's propulsion system and its structure that can become dangerously unstable.",
        "Specific Impulse (ISP) is a measure of rocket-engine efficiency, roughly analogous to fuel economy for a car.",
        "Astronauts on the International Space Station witness 16 sunrises and sunsets every single day.",
        "Liquid Hydrogen fuel is so cold (-423°F) that it would instantly freeze air into a solid block of nitrogen ice.",
        "Ion thrusters can produce only about as much thrust as the weight of a sheet of paper, but can run continuously for months or years.",
        "Orbit is not about being high above Earth. It is about falling toward Earth fast enough that the ground keeps curving away.",
        "A rocket heading straight up would quickly fall back down. Orbital rockets spend most of their energy building sideways speed.",
        "Some rocket engines can restart in space, allowing one launch to send satellites into several different orbits.",



    ]

    facts = []
    if "falcon 9" in r_name:
        facts = [
            "SpaceX's Falcon 9 uses grid fins cast from a single piece of titanium so strong they are rarely replaced.",
            "The Falcon 9 cannot hover; it must perform a 'hoverslam' to hit zero velocity exactly at touchdown.",
            "Falcon 9 uses densified, subcooled liquid oxygen and RP-1 so more propellant can fit inside the same tanks.",
            "Falcon 9 uses friction stir welding to fuse its aluminum-lithium tanks without melting the metal.",
            "The Falcon 9 fairing halves are guided back to Earth using onboard thrusters and parafoils to be recovered from the ocean.",
            "Falcon 9 fairings are recovered and reused. SpaceX says it began reflighting fairings in 2019.",
            "The Falcon 9 is transported horizontally on the road, pressurized with nitrogen to keep the thin tanks rigid.",
            "The soot on a landed Falcon 9 is rarely cleaned off fully, giving flight-proven boosters a distinct dirty look.",
            "Falcon 9 uses sub-cooled propellants, meaning the fuel is chilled near its freezing point to increase density.",
            "SpaceX's Falcon 9 is the first orbital class rocket capable of reflight.",
            "The Falcon 9 telemetry signal often cuts out right at landing due to the vibration of the landing burn shaking the antenna.",
            "Falcon 9's first stage has nine Merlin engines, but the rocket can keep flying even after losing an engine during ascent.",
            "Falcon 9's first stage flips around after separation and fires its engines again to fly back toward Earth.",
            "Falcon 9 can land on a drone ship hundreds of kilometres downrange when returning to the launch site would take too much fuel.",
        ]
    elif "falcon heavy" in r_name:
        facts = [
            "Falcon Heavy is essentially three Falcon 9 first stages strapped together, giving it 27 engines at liftoff.",
            "The Falcon Heavy's center booster is heavily reinforced with thicker tank walls to withstand the force of the side boosters.",
            "Falcon Heavy's first payload, a Tesla Roadster, was thrown into an orbit that crosses the path of Mars.",
            "The Falcon Heavy's 27 engines do not ignite instantly but are staggered by milliseconds to reduce acoustic shock.",
            "SpaceX often converts flight-proven Falcon 9 boosters to serve as side boosters for the Falcon Heavy.",
            "The Falcon Heavy's center core throttles down almost immediately after launch to save fuel for the later stages.",
            "The launch pad's 'rainbird' sound suppression system had to be upgraded to handle Falcon Heavy's acoustic energy.",
            "The three exhaust plumes of the Falcon Heavy interact to create a visible, massive single column of fire.",
            "Falcon Heavy has more thrust at liftoff than eighteen 747 aircraft at full power.",
            "Falcon Heavy can lift nearly 64 metric tonnes to low Earth orbit in an expendable configuration.",
            "Falcon Heavy was originally designed to carry humans to the Moon, but Starship has taken over that role.",
            "The side boosters of Falcon Heavy perform a 'boostback burn' to return to the launch site, creating a spectacular light show.",
            "Falcon Heavy's second stage can restart multiple times to deliver payloads to complex geostationary orbits.",
            "The sound of a Falcon Heavy launch is so loud it can be felt physically miles away from the pad.",
            "The two side boosters land almost simultaneously, creating a double sonic boom heard across the coast.",
            "Falcon Heavy uses a modified transporter-erector at LC-39A to handle the wider fuselage.",
            "Unlike the side boosters, the center core of Falcon Heavy usually lands downrange on a drone ship due to high velocity.",
        ]
    elif "starship" in r_name:
        facts = [
            "Starship is designed to be fully reusable, including both its Super Heavy booster and Starship upper stage.",
            "Starship uses Liquid Methane fuel, which can theoretically be synthesized from the Martian atmosphere.",
            "SpaceX catches the returning Super Heavy booster using massive 'Mechazilla' chopstick arms.",
            "Starship uses ceramic hexagonal heat tiles that are mechanically attached to shift as the steel tank expands.",
            "The Raptor engine uses a Full-Flow Staged Combustion cycle, a complex design only previously attempted by Soviet engineers.",
            "Starship is pressurized with autogenous gas (gaseous methane/oxygen) instead of heavy helium bottles.",
            "Starship is constructed from stainless steel rather than carbon fiber to better withstand reentry heat.",
            "Starship is designed to be refuelled in orbit, making much longer journeys to the Moon or Mars possible.",
            "Starship is 9 metres wide, more than twice the diameter of a Falcon 9.",
        ]
    elif "electron" in r_name:
        facts = [
            "Rocket Lab's Electron is the only orbital rocket that uses battery-powered electric motors to spin its fuel pumps.",
            "Electron drops depleted battery packs during flight, reducing the mass it has to accelerate.",
            "Rocket Lab's Rutherford engines are almost entirely 3D printed, allowing a verified engine to be built in 24 hours.",
            "The Electron's body is black because it is made of carbon fiber composite, making it light enough for two people to lift.",
            "Rocket Lab's Electron controllers run on C++ code, similar to the software powering many video games.",
            "The Rutherford engine uses an electric motor the size of a soda can to spin its pumps at 40,000 RPM.",
            "Rocket Lab names their Electron missions with puns, such as 'It's a Business Time' and 'Rocket Like a Hurricane'.",
            "Electron's exhaust sometimes appears to sparkle because the ablative liner of the engine nozzle erodes intentionally.",
            "Rocket Lab's Electron is surprisingly small, measuring only about 1.2 metres (4 feet) in diameter.",
        ]
    elif "atlas v" in r_name:
        if "n22" in r_name:
            facts = [
                "The Atlas V N22 is unique because it has no payload fairing; the Starliner capsule sits directly on top.",
                "The 'N' in N22 stands for 'No Fairing', while '22' means 2 boosters and 2 Centaur engines.",
                "Atlas V N22 uses a Dual Engine Centaur (DEC), a configuration not used since the Atlas II era.",
                "An 'Aeroskirt' is attached to the Atlas V N22 to smooth the airflow over the Starliner/Centaur connection.",
                "This specific Atlas V configuration is human-rated to carry astronauts to the ISS.",
                "The N22's two solid rocket boosters are made by Aerojet Rocketdyne (AJ-60A) or Northrop Grumman (GEM 63).",
                "Atlas V N22 does not use a launch escape tower; Starliner's abort engines are built into the capsule.",
                "The dual-engine Centaur on the N22 provides a flatter trajectory, safer for crew abort scenarios.",
            ]
        elif "551" in r_name:
            facts = [
                "Atlas V 551 launched the New Horizons probe, the fastest object ever launched from Earth at that time.",
                "The '551' code means: 5-meter fairing, 5 solid boosters, and 1 Centaur engine.",
                "Because it has 5 boosters, the Atlas V 551 is asymmetrical and requires significant engine gimbaling.",
                "This configuration launched the Juno spacecraft to Jupiter.",
                "The 5 solid boosters provide nearly 2 million pounds of thrust at liftoff.",
                "Atlas V 551 weighs about 1.2 million pounds (569,000 kg) fully fueled on the pad.",
                "The 5-meter fairing on the 551 is made of carbon fiber composites by RUAG Space.",
            ]
        else:
            facts = [
                "The Atlas V launched NASA's Mars Perseverance Rover and the New Horizons Pluto probe.",
                "Atlas V's RD-180 main engine is a high-performance Russian engine known for its efficiency.",
                "Atlas V flies a remarkably steep trajectory compared to other rockets to get out of the thick atmosphere quickly.",
                "The Atlas V 500 series flies with an offset fairing, making the rocket look slightly asymmetrical on the pad.",
                "Atlas V can fly with anywhere from 0 to 5 solid rocket boosters depending on the payload weight.",
            ]
    elif "vulcan" in r_name:
        facts = [
            "The Vulcan Centaur's stainless steel upper tank is as thin as a dime.",
            "The Vulcan SMART reuse plan involves catching just the engines after splashdown.",
            "Vulcan uses Blue Origin BE-4 engines, relying on hardware from a competitor.",
            "Vulcan stages travel by ship (RocketShip) because they are too big for roads.",
            "The Centaur upper stage engine lineage dates back to the 1960s.",
            "The Vulcan main tank uses an 'orthogrid' milled pattern for strength.",
        ]
    elif "new glenn" in r_name:
        facts = [
            "Blue Origin's New Glenn is designed to land on a moving ship that drives forward to stabilize against waves.",
            "The New Glenn payload fairing is so voluminous that three full-sized school buses could fit inside side-by-side.",
            "New Glenn's BE-4 engine uses an oxygen-rich staged combustion cycle, a method that requires advanced metallurgy.",
            "The feather logo on Blue Origin's New Glenn represents the perfection of flight, inspired by Apollo 15.",
            "Blue Origin's New Glenn first stage landing gear is passive, absorbing impact without complex hydraulics.",
            "New Glenn uses a 'tapped off' gas system to pressurize tanks, eliminating the need for heavy helium bottles.",
            "The New Glenn booster uses wing-like strakes to provide aerodynamic lift during its return glide.",
            "New Glenn is assembled vertically in a massive hangar to protect delicate satellite payloads.",
        ]
    elif "soyuz" in r_name:
        facts = [
            "Roscosmos's Soyuz engines are ignited by pyrotechnics held in place by birch or hazel wood sticks.",
            "The Soyuz rocket hangs suspended in a 'Tulip' structure rather than bolting to the pad.",
            "The official Soyuz launch command is ceremonially called 'Key to Start', a holdover from early designs.",
            "The Soyuz launch key is a small command tool inserted into a bunker console, not a car-style ignition key.",
            "The Soyuz 'periscope' used by the crew for docking alignment is a literal system of mirrors sticking out of the capsule.",
            "Soyuz crew buses stop for a traditional 'urination ritual' on the rear wheel on the way to the pad.",
            "The Soyuz abort tower motors pull 14Gs, moving the crew away faster than the human eye can track.",
            "Soyuz boosters separate in the famous 'Korolev Cross' pattern caused by residual oxygen venting.",
        ]
    elif "ariane 62" in r_name:
        facts = [
            "Ariane 62 is the medium-lift variant of Europe's new launcher, equipped with two solid boosters.",
            "The Ariane 62 variant is specifically optimized for government and scientific missions that don't need heavy lift capability.",
            "Ariane 62 can lift about 4.5 tonnes to Geostationary Transfer Orbit (GTO).",
            "Ariane 62 replaces the role previously filled by the Russian Soyuz rocket launched from French Guiana.",
            "The launch cost of an Ariane 62 is targeted to be roughly half that of its predecessor.",
        ]
    elif "ariane 64" in r_name:
        facts = [
            "Ariane 64 is the heavy-lift configuration, boasting four solid rocket boosters.",
            "The Ariane 64 is designed primarily for dual-launch commercial missions, carrying two heavy satellites at once.",
            "Ariane 64 can deliver 11.5 tonnes to Geostationary Transfer Orbit, rivaling heavy commercial competitors.",
            "Ariane 64 uses a larger 20-meter payload fairing to accommodate bulky satellite constellations.",
            "The modular design allows Arianespace to swap from 62 to 64 configuration relatively quickly.",
            "Ariane 64's upper stage can perform a de-orbit burn to prevent space debris after mission completion.",
        ]
    elif "ariane 6" in r_name:
        facts = [
            "ESA's Ariane 6 components are transported to French Guiana on a ship called 'Canopée' that uses massive wingsails.",
            "Ariane 6 is assembled horizontally to save time and money, unlike its predecessor Ariane 5.",
            "The Ariane 6 upper stage features a tiny auxiliary engine that re-ignites to settle the fuel in orbit.",
            "Ariane 6's Vinci engine can restart up to 5 times in orbit, allowing it to de-orbit itself to prevent space debris.",
            "Ariane 6's launch pad can dump roughly a quarter of an Olympic-sized swimming pool of water onto the pad in about 20 seconds to suppress acoustic shock.",
            "Launching Ariane 6 from French Guiana provides a 'slingshot' speed boost of nearly 1,000 mph due to Earth's rotation.",
        ]
    elif "spectrum" in r_name or "isar" in r_name:
        facts = [
            "Isar Aerospace's Spectrum is Germany's first privately developed orbital launch vehicle.",
            "Spectrum is designed to lift up to 1,000 kg to Sun-Synchronous Orbit, targeting the small satellite market.",
            "Spectrum's engines run on liquid oxygen and propane, a cleaner alternative to traditional kerosene.",
            "Isar Aerospace is named after the Isar River that flows through Munich, where the company is headquartered.",
            "Spectrum features a modular design that allows rapid reconfiguration for different mission profiles.",
            "The Spectrum rocket stands 28 meters tall, roughly the height of a 9-story building.",
        ]
    elif "long march 12" in r_name:
        facts = [
            "Long March 12 is designed to lift at least 10 tonnes to Low Earth Orbit.",
            "Long March 12 uses a completely new launch pad designed for rapid commercial launch cadence.",
            "Long March 12's YF-100K engines are upgraded versions of the engines used on the Long March 7.",
            "The 3.8m diameter allows the Long March 12 to be transported by rail, unlike the sea-only Long March 5.",
            "Long March 12 is a key player in China's growing commercial satellite internet plans.",
        ]
    elif "long march 5" in r_name:
        facts = [
            "CASC's Long March 5 is nicknamed 'Fat-Five' because its diameter broke the limits of Chinese railway tunnels.",
            "Long March 5 is the first Chinese rocket that must be transported by ship to the launch site.",
            "The Long March 5 uses YF-100 engines that run on an Oxygen-Rich Staged Combustion cycle.",
            "The Long March 5 core stage is so cold after fueling that it creates its own weather system of fog.",
            "CASC's Long March 5 appears to change color from orange to white as frost shakes off during launch.",
            "The Long March 5 fairing was large enough to launch the Tiangong space station core module in one piece.",
            "Ten liquid engines fire simultaneously at the liftoff of a Long March 5.",
        ]
    elif "long march 7" in r_name:
        facts = [
            "CASC's Long March 7 is the primary cargo truck for the Tiangong Space Station.",
            "Long March 7 uses non-toxic kerosene/LOX, replacing older hypergolic rockets.",
            "Long March 7 launches exclusively from the coastal Wenchang Space Launch Site.",
            "Long March 7 uses four massive strap-on boosters that are liquid-fueled.",
            "Long March 7 uses high-pressure staged combustion engines (YF-100).",
            "Long March 7 uses a totally digital flight control system.",
        ]
    elif "long march 6a" in r_name:
        facts = [
            "Long March 6A is China's first rocket to combine liquid-fueled core stages with solid-fueled strap-on boosters.",
            "The four solid boosters on Long March 6A provide extra thrust at liftoff before being jettisoned.",
            "Long March 6A uses a 'smart' health monitoring system to automatically diagnose issues before launch.",
            "The Long March 6A launches from a dedicated complex in Taiyuan that features a fixed umbilical tower and rotary launch platform.",
            "Long March 6A bridges the gap between medium and heavy-lift vehicles in the Chinese fleet.",
        ]
    elif "long march 2d" in r_name:
        facts = [
            "Known as a 'Gold Medal Rocket', Long March 2D has an exceptionally high reliability record over 30+ years.",
            "Long March 2D is widely used for Earth-observation and remote-sensing satellites.",
            "Long March 2D uses toxic hypergolic propellants, which explains the reddish smoke often seen at liftoff.",
            "Long March 2D can launch multiple small satellites in a single mission using a specialized dispenser.",
        ]
    elif "delta" in r_name:
        facts = [
            "Delta IV Heavy sets itself on fire at launch to burn off excess hydrogen.",
            "Delta IV Heavy was the most powerful rocket in the world before Falcon Heavy.",
            "Delta IV Heavy launches massive NRO spy satellites.",
            "Delta IV Heavy uses three Common Booster Cores bolted together.",
            "Delta IV Heavy engines run on liquid hydrogen, creating a clear flame.",
        ]
    elif "pslv" in r_name:
        facts = [
            "ISRO's PSLV is known as the 'Workhorse of India' for its high reliability.",
            "PSLV launched India's first mission to Mars (Mangalyaan).",
            "PSLV alternates solid and liquid stages (Solid-Liquid-Solid-Liquid).",
            "PSLV set a world record by launching 104 satellites in a single mission.",
            "PSLV uses strap-on boosters that look like miniature rockets.",
        ]
    elif "vega" in r_name:
        facts = [
            "ESA's Vega is named after the second brightest star in the northern hemisphere.",
            "Vega is composed mostly of solid-fuel stages.",
            "Vega launches from the same jungle spaceport as Ariane 6.",
            "Vega is designed specifically for small scientific and earth observation satellites.",
        ]
    elif "h3" in r_name:
        facts = [
            "H3 uses a complex 'expander bleed cycle' scaled up for main engines.",
            "H3 uses commercial technology from industries such as automotive manufacturing to reduce cost.",
            "The H3 rocket is bolted to the platform and rolls 500m to the pad.",
            "The H3 flight computer can trigger self-destruct if ignition fails.",
            "H3 insulation is sprayed-on silicone instead of hand-glued cork.",
            "H3 can coast for hours to insert directly to Geostationary Orbit.",
            "H3 Pogo suppression is built into the piping geometry.",
            "H3 launches from Tanegashima, considered the world's most beautiful launch site.",
        ]
    elif "lvm3" in r_name:
        facts = [
            "ISRO's LVM3 is affectionately nicknamed 'Bahubali' or 'Fat Boy' due to its stubby appearance.",
            "The S200 solid boosters on ISRO's LVM3 use a flex-nozzle control system where the entire nozzle pivots.",
            "ISRO paints the LVM3 white to reflect tropical sunlight and keep the fuel tanks cool on the launch pad.",
            "The LVM3's solid boosters are among the largest in the world, each containing 205 tons of propellant.",
            "ISRO's LVM3 cryogenic upper stage engine was developed entirely indigenously in India.",
            "The LVM3 launch pad uses a water suppression system that keeps the acoustic energy below 142 decibels.",
            "ISRO's LVM3 liquid core engines do not ignite until the rocket is about 113 seconds into the flight.",
        ]
    elif "gslv" in r_name:
        facts = [
            "GSLV Mk II is affectionately nicknamed the 'Naughty Boy' by ISRO due to early reliability issues.",
            "The GSLV Mk II features an indigenously developed Cryogenic Upper Stage (CUS).",
            "GSLV Mk II uses four liquid strap-on boosters derived from the PSLV's core stage.",
            "The GSLV Mk II is designed primarily to launch INSAT communication satellites.",
        ]
    elif "proton" in r_name:
        facts = [
            "The Proton rocket uses toxic hypergolic propellants that ignite on contact.",
            "Proton has launched every Soviet and Russian space station module, including Mir.",
            "The Proton rocket is transported horizontally by rail and erected at the launch pad.",
            "Proton uses a Briz-M upper stage that can restart multiple times.",
        ]
    elif "angara" in r_name:
        facts = [
            "Angara is the first all-new launch vehicle family developed by Russia since the Soviet era.",
            "Angara uses Universal Rocket Modules (URMs) that can be strapped together.",
            "Angara burns clean kerosene and oxygen, replacing the toxic Proton rocket.",
        ]
    elif "antares" in r_name:
        facts = [
            "Antares is designed specifically to launch the Cygnus cargo spacecraft to the ISS.",
            "The Antares first stage was built in Ukraine, while its engines were originally Russian.",
            "Antares launches from Wallops Island, Virginia, visible to the US East Coast.",
        ]
    elif "minotaur" in r_name:
        facts = [
            "Minotaur rockets are built from decommissioned Minuteman and Peacekeeper ICBM stages.",
            "The Minotaur I can be assembled and launched in weeks due to its solid-fuel design.",
            "Minotaur launches often look different because they use a yellow-flamed solid propellant.",
        ]
    elif "firefly" in r_name:
        facts = [
            "Firefly Alpha's Reaver engines use a 'combustion tap-off' cycle, a rare design.",
            "The Firefly Alpha airframe is built entirely from carbon-fiber composite.",
            "Firefly Alpha launched the 'Victus Nox' mission with just 27 hours of notice.",
        ]
    elif "sls" in r_name or "artemis" in r_name:
        facts = [
            "NASA's SLS Block 1 produces 8.8 million pounds of thrust, which is 15% more power than the legendary Saturn V.",
            "The SLS core stage stores 733,000 gallons of super-cooled liquid hydrogen and liquid oxygen.",
            "SLS uses four RS-25 engines that are refurbished veterans from the Space Shuttle program.",
            "The twin solid rocket boosters on SLS provide more than 75% of the total thrust during the first two minutes.",
            "SLS is designed to be evolvable, with future variants planning to lift up to 130 metric tons.",
            "The SLS solid boosters are five-segment versions of the Shuttle boosters, adding 25% more impulse.",
            "SLS stands 322 feet tall, taller than the Statue of Liberty but slightly shorter than Saturn V.",
            "The core stage uses friction stir welding for its barrel sections, creating stronger bonds.",
            "SLS is capable of sending the Orion spacecraft and four astronauts directly to the Moon.",
            "The propellant for the SLS solid boosters has the consistency of a rubber eraser.",
        ]
    elif "long march 2f" in r_name:
        facts = [
            "The Long March 2F is nicknamed 'Shenjian' (Divine Arrow) and is used for China's crewed missions.",
            "Long March 2F features an advanced fault monitoring system to trigger the launch escape tower.",
            "Unlike other Long March variants, the 2F is assembled vertically and rolled out upright.",
            "Long March 2F uses redundant control systems to ensure crew safety.",
            "The launch escape tower is jettisoned exactly 2 minutes into the flight if no emergency occurs.",
            "Long March 2F has achieved a perfect success rate, launching every Chinese astronaut since 2003.",
            "The 2F/G variant features improved grid fins to guide boosters to a safe zone.",
            "Long March 2F's payload fairing is equipped with solid rockets for abort scenarios.",
            "Incremental upgrades have reduced the vibration on the Long March 2F by 50%.",
            "Crew members can exit the launch pad via a canvas slide into an underground shelter.",
        ]
    elif "long march 3b" in r_name:
        facts = [
            "Long March 3B is China's primary workhorse for high-orbit Geostationary missions.",
            "Long March 3B uses hypergolic propellants which can be stored at room temperature.",
            "The Long March 3B features four liquid-fueled strap-on boosters.",
            "Long March 3B's third stage uses cryogenic liquid hydrogen and liquid oxygen engines.",
            "Long March 3B launched the Chang'e 3 lunar lander and Yutu rover to the Moon.",
            "The 3B/E variant has a larger first stage and boosters for increased payload.",
            "Long March 3B has launched over 100 missions, making it a fleet staple.",
            "It launches from Xichang, meaning spent stages often fall over land.",
            "Long March 3B was crucial for building China's BeiDou Navigation Satellite System.",
            "After an early failure in 1996, the Long March 3B has become highly reliable.",
        ]
    elif "nuri" in r_name:
        facts = [
            "Nuri is the first orbital launch vehicle developed entirely with indigenous South Korean technology.",
            "Unlike its predecessor Naro-1, every component of Nuri was built in South Korea.",
            "Nuri is designed to launch 1.5-ton payloads into Sun-Synchronous Orbit.",
            "The KRE-075 engines on Nuri run on Jet A-1 kerosene and Liquid Oxygen.",
            "South Korea plans to use Nuri technology to launch a lunar lander by 2031.",
            "Nuri's launch complex at Naro Space Center was built specifically for this rocket.",
            "Nuri successfully deployed a performance verification satellite and CubeSats in 2022.",
            "Nuri stands 47.2 meters tall, roughly the height of a 15-story building.",
        ]
    elif "ceres-2" in r_name:
        facts = [
            "Ceres-2 is an evolved version of Ceres-1 with significantly higher payload capacity.",
            "Unlike the solid-upper-stage Ceres-1, Ceres-2 features a liquid fourth stage for precision orbits.",
            "Ceres-2 is designed to launch 2,000 kg to Low Earth Orbit, a major upgrade from Ceres-1.",
            "Ceres-2 targets the growing medium-class satellite constellation market in China.",
            "Galactic Energy developed Ceres-2 to compete directly with Long March 6 and 11.",
            "The liquid upper stage allows Ceres-2 to deploy multiple satellites into different orbits in one mission.",
            "Ceres-2 maintains the mobile launch capability of its predecessor.",
            "Ceres-2 is one of the few private Chinese rockets capable of lifting over 1.5 tonnes.",
            "Ceres-2 aims to launch from both land pads and sea platforms.",
        ]
    elif "ceres" in r_name:
        facts = [
            "Ceres-1 is named after the first asteroid discovered, the Roman goddess of agriculture.",
            "Ceres-1 is a four-stage rocket with three solid stages and one liquid upper stage.",
            "Ceres-1 can be launched from a mobile transporter or a sea-launch barge.",
            "The Ceres-1S is a sea-launched variant that debuted from a barge in the Yellow Sea.",
            "Ceres-1 is surprisingly small, standing only 19 meters tall.",
            "The fourth stage uses a hydrazine propulsion system for accurate injection.",
            "Ceres-1's solid motors allow it to launch quickly for rapid response.",
            "Galactic Energy was the second private Chinese firm to ever reach orbit.",
            "Ceres-1 can lift about 400 kg to Low Earth Orbit.",
        ]
    elif "hanbit" in r_name:
        facts = [
            "Hanbit-Nano is South Korea's first commercial launch vehicle, built by the startup Innospace.",
            "Hanbit-Nano uses a unique Hybrid Rocket Engine that burns solid paraffin (wax) fuel with liquid oxygen.",
            "Hanbit-Nano's hybrid engine design allows it to be throttled and even shut down safely in an emergency.",
            "Hanbit-Nano is designed for the rapid-response small satellite market.",
            "Hanbit-Nano's fuel is essentially high-grade candle wax, making it much safer to handle than traditional rocket fuels.",
            "Its name 'Hanbit' means 'One Light' or 'Great Light' in Korean.",
        ]
    elif "zhuque-3" in r_name or "zq-3" in r_name:
        facts = [
            "Zhuque-3 is China's first stainless steel rocket, built the same way SpaceX builds Starship.",
            "Zhuque-3's first stage is designed to fly again, landing on a pad downrange in the Gansu desert.",
            "Zhuque-3 is taller than any other Chinese commercial rocket flying today.",
            "Zhuque-3 is built by LandSpace, a private company founded in 2015, not by the Chinese state.",
            "Zhuque-3 burns methane and liquid oxygen, which leaves engines far cleaner than kerosene does.",
            "Zhuque means 'Vermilion Bird', one of the four guardian creatures of Chinese constellations.",
        ]
    elif "zhuque" in r_name or "zq-2" in r_name:
        facts = [
            "Zhuque-2 was the first liquid-methane-fueled rocket in the world to reach orbit, beating both SpaceX and Blue Origin to it.",
            "Zhuque-2 is built by LandSpace, one of the first Chinese private companies licensed to build orbital rockets.",
            "Methane engines can be reused far more often than kerosene ones, because kerosene leaves soot behind.",
            "Zhuque-2's upgraded 2E variant lifts about 50% more payload than the original.",
        ]
    elif "kinetica" in r_name or "lijian" in r_name:
        facts = [
            "Kinetica-1 is a solid-fueled rocket, so it can sit fueled and ready for long periods before launch.",
            "Kinetica-1 is built by CAS Space, a spinoff of the Chinese Academy of Sciences.",
            "Its Chinese name Lijian means 'strong arrow'.",
        ]
    elif "tianlong" in r_name:
        facts = [
            "Tianlong-3 is designed by Space Pioneer to launch China's answer to Starlink.",
            "Tianlong-3's first stage is intended to be recovered and reflown.",
            "In 2024 a Tianlong-3 static fire test went wrong and the rocket tore free of its stand and flew briefly before crashing.",
            "Tianlong means 'heavenly dragon'.",
        ]
    elif "gravity-1" in r_name or "yinli" in r_name:
        facts = [
            "Gravity-1 launches from a ship at sea rather than from a pad, so it can move to suit the orbit it needs.",
            "Gravity-1's first launch in 2024 made it the world's most powerful solid-fuel launch vehicle at the time.",
            "Gravity-1 is built by Orienspace, a Chinese company founded in 2020.",
            "Gravity-1's Chinese name Yinli means 'gravity', the thing every rocket is built to escape.",
        ]
    elif "neutron" in r_name:
        facts = [
            "Neutron's fairing stays attached to the rocket and opens like a flower, then closes again for the trip home.",
            "Neutron is built largely from carbon composite rather than metal, to save weight.",
            "Neutron is Rocket Lab's answer to the Falcon 9, sized for constellation launches.",
            "Neutron's upper stage hangs inside the first stage rather than sitting on top of it.",
        ]
    elif "long march 2c" in r_name:
        facts = [
            "The Long March 2C first flew in 1982 and is still in service, making it one of the longest-serving rockets anywhere.",
            "The Long March 2C burns hypergolic propellants, which ignite on contact and need no ignition system at all.",
            "Those same propellants are highly toxic, which is why launch crews wear full protective suits.",
            "The Long March 2C has flown from all four of China's launch sites.",
        ]
    elif "long march 8" in r_name:
        facts = [
            "The Long March 8 was designed from the start for China's satellite constellation programs.",
            "The Long March 8 burns kerosene and liquid oxygen, far cleaner than the older hypergolic Long March rockets.",
            "A version of the Long March 8 flies with no strap-on boosters at all, for lighter payloads.",
            "The Long March 8 flies from Wenchang, China's newest and most southerly launch site.",
        ]
    elif "long march 4" in r_name:
        facts = [
            "The Long March 4 family specialises in sun-synchronous orbits, where a satellite passes over the same spot at the same local time every day.",
            "The Long March 4B and 4C are three-stage rockets built for Earth observation and weather satellites.",
            "The Long March 4C's third stage can restart in flight, which the 4B's cannot.",
            "The Long March 4 family flies mostly from Taiyuan, in the mountains of Shanxi province.",
        ]
    elif "long march 11" in r_name:
        facts = [
            "Long March 11 is a solid-fueled member of the Long March family designed for rapid-response launches.",
            "The Long March 11 has launched from a converted barge in the Yellow Sea.",
            "At under 21 meters the Long March 11 is by far the smallest rocket in the Long March family.",
        ]
    elif "long march 3" in r_name:
        facts = [
            "The Long March 3 family carries most of China's satellites to geostationary orbit, 36,000 km up.",
            "The Long March 3B is China's most-flown rocket to high orbit, with four strap-on boosters.",
            "The Long March 3 family's third stage burns liquid hydrogen, which must be kept below minus 253 degrees.",
            "Long March 3 rockets launch from Xichang, deep in the mountains of Sichuan.",
        ]
    elif "long march" in r_name:
        facts = [
            "The Long March family is named after the Chinese Red Army's 9,000 km retreat in 1934.",
            "The Long March family has flown more than 600 times since 1970.",
            "Long March rockets have launched from four sites: Jiuquan, Taiyuan, Xichang and Wenchang.",
            "The older Long March rockets burn hypergolic propellants that ignite on contact, needing no ignition system.",
        ]
    elif "new shepard" in r_name:
        facts = [
            "New Shepard is named after Alan Shepard, the first American to go to space.",
            "New Shepard is fully reusable: the booster lands vertically, and the capsule lands with parachutes.",
            "New Shepard's crew capsule features the largest windows ever flown in space, offering 360-degree views.",
            "New Shepard is designed for suborbital tourism, taking passengers just above the 100km Kármán line.",
            "New Shepard's entire flight lasts only about 11 minutes from liftoff to touchdown.",
            "New Shepard's booster uses a single BE-3 engine that runs on liquid hydrogen and oxygen, emitting only steam.",
            "New Shepard's capsule has a solid-rocket escape motor in the center that can blast the crew to safety in milliseconds.",
        ]

    pool = facts + general_facts if facts else general_facts

    try:
        return random.Random(f"{seed}|{rocket_name}").choice(pool)
    except (IndexError, KeyError) as e:
        print(f"Warning: Fact selection failed for {rocket_name}: {e}")
        return "Rockets are cool."

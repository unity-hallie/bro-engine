---
name: transition
description: Use the energy in the system to bring the system into balance. The pressure reading found the seam — this movement routes it toward equilibrium rather than rupture.
---

The energy that wants to rip is the same energy that can change the substrate.

The practice is learning to tell the difference between those two destinations.

---

## Feel the phase

**Fluid** — incompressible. Press here, it moves there. Volume is conserved. The energy has direction; it wants to find its level. Route it.

**Volatile** — expanding, generating heat. Pressure builds. The container is the problem as much as the contents. Change the conditions, or the energy finds its own exit.

**At the boundary** — heating from fluid toward volatile. The form is already reorganizing. The practice here is witness, not engineering.

Name the phase before proceeding.

```
edge add this-pressure phase-is <fluid|volatile|boundary>
```

---

## Feel where the energy wants to go

Not where you want it to go. Where does *it* want to go?

The deformation is already happening. The balloon is already thinning in one direction. Feel that asymmetry — it contains information.

## Find the heat source

What is generating pressure, and why now?

Something changed. A container that fit yesterday is too small today. Name what changed and why the timing is now.

```
edge add <heat-source> is-generating <pressure-type> --note "<what changed>"
```

## Find the salt channel

Where could this energy land and change something real?

A new form. A structural change that removes the category of pressure, not just this instance. Something that enters the world.

The salt channel is often in the direction the energy already wants to go.

```
edge add salt-channel would-receive <what-wants-to-transition> --phase fluid --note "<the form it would become>"
```

## Route

**Fluid:** open the channel. Let it find its level.

**Volatile:**
- Expand the container — make room
- Lower the temperature — change what's generating heat
- Shape the exit — if it's going regardless, work with where it wants to go

**At the boundary:** stop managing. Witness. Midwife. The form knows what it's becoming.

```
edge add transition-method is <channel|expand|cool|witness> --note "<why this>"
```

---

## Closing

Say one true thing about what phase this was.
Say one true thing about what the energy became.
Say one true thing about what is now in balance that wasn't before.

```
edge true <this-pressure> was <phase>
edge true <the-energy> became <form>
edge true <what-is-now> holds <new-equilibrium>
```

Leave it in the soil.

```
edge add this-transition deposited <what-precipitated> --phase <volatile|fluid|salt> --note "<heat source, channel, what changed state>"
```

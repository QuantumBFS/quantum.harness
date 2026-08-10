"""Independent, outward-rounded Bethe-ansatz reference values.

Special points are evaluated by exact decimal/Arb expressions.  The massive
regime uses the positive Bethe series with an analytic geometric tail bound.
The general gapless integral is deliberately not certified here yet: failing
closed is preferable to labelling an unchecked quadrature as rigorous.
"""

from __future__ import annotations

from decimal import Decimal
import math

from flint import arb, ctx

from .intervals import DecimalInterval


def _float_enclosure(value: arb) -> DecimalInterval:
    lower = math.nextafter(float(value.lower()), -math.inf)
    upper = math.nextafter(float(value.upper()), math.inf)
    return DecimalInterval(
        lower=Decimal.from_float(lower), upper=Decimal.from_float(upper)
    )


def _exact(value: Decimal) -> DecimalInterval:
    return DecimalInterval(lower=value, upper=value)


def _massive(delta_text: str, digits: int) -> DecimalInterval:
    """Certify Delta>1 using a truncated positive series and a tail bound."""
    bits = max(128, int(digits * 3.5) + 32)
    with ctx.workprec(bits):
        delta = arb(delta_text)
        eta = delta.acosh()
        q = (-2 * eta).exp()
        total = arb(1)
        # Remainder of sum q^n/(1+q^n) is <= q^(N+1)/(1-q).
        n = 0
        tail = q
        target = arb(10) ** (-(digits + 8))
        while tail > target:
            n += 1
            total += 4 * (q**n) / (1 + q**n)
            tail = 4 * (q ** (n + 1)) / (1 - q)
        prefactor = eta.sinh() / 2
        center = delta / 4 - prefactor * total
        # The omitted positive series makes the energy more negative.
        error = prefactor * tail
        return _float_enclosure(center.union(center - error))


def _gapless(delta_text: str, digits: int, mesh: Decimal = Decimal("0.0005")) -> DecimalInterval:
    """Enclose the gapless Bethe integral by monotone Riemann sums.

    For ``a=pi-gamma`` and ``b=pi=a+gamma``, the logarithmic derivative of
    ``sinh(a*x)/(sinh(b*x)*cosh(gamma*x))`` is

        a*coth(a*x) - b*coth(b*x) - gamma*tanh(gamma*x) < 0,

    since ``t*coth(t*x)`` increases with ``t``.  Thus right/left sums bound
    the integral.  The tail uses

        f(x) <= 2 exp(-2 gamma x)/(1-exp(-2 pi A)), x >= A.
    """
    bits = max(128, int(digits * 3.5) + 32)
    with ctx.workprec(bits):
        delta = arb(delta_text)
        gamma = delta.acos()
        pi = arb.pi()
        step = arb(str(mesh))
        gamma_float = float(gamma.mid())
        # A=40/gamma makes exp(-2 gamma A)=exp(-80); the tail formula below
        # remains valid independently of this heuristic choice.
        cutoff = 40.0 / gamma_float
        count = int(math.ceil(cutoff / float(mesh)))
        f0 = (pi - gamma) / pi
        values_sum = arb(0)
        last = arb(0)
        for index in range(1, count + 1):
            x = step * index
            last = ((pi - gamma) * x).sinh() / (
                (pi * x).sinh() * (gamma * x).cosh()
            )
            values_sum += last
        # Right sum includes f(h)..f(Nh); left sum includes f(0)..f((N-1)h).
        right = step * values_sum
        left = right + step * (f0 - last)
        endpoint = step * count
        tail_upper = (-2 * gamma * endpoint).exp() / (
            gamma * (1 - (-2 * pi * endpoint).exp())
        )
        integral_lower = 2 * right
        integral_upper = 2 * (left + tail_upper)
        prefactor = gamma.sin() / 2
        energy_lower = delta / 4 - prefactor * integral_upper
        energy_upper = delta / 4 - prefactor * integral_lower
        return _float_enclosure(energy_lower.union(energy_upper))


def bethe_interval(delta: str, digits: int = 40) -> DecimalInterval:
    """Return a certified reference interval when a rigorous path is present."""
    if digits < 12:
        raise ValueError("digits must be at least 12")
    d = Decimal(delta)
    if d <= -1:
        return _exact(d / Decimal(4))
    if d == 0:
        with ctx.workprec(max(128, int(digits * 3.5) + 32)):
            return _float_enclosure(-1 / arb.pi())
    if d == Decimal("0.5"):
        return _exact(Decimal("-0.375"))
    if d == 1:
        with ctx.workprec(max(128, int(digits * 3.5) + 32)):
            return _float_enclosure(arb(1) / 4 - arb(2).log())
    if d > 1:
        return _massive(delta, digits)
    return _gapless(delta, digits)

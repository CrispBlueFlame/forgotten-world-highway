#!/usr/bin/env python3
"""NZTM2000 (EPSG:2193) -> WGS84 inverse transverse Mercator. No pyproj on this box.

Parameters per LINZ: GRS80, central meridian 173E, origin lat 0, false easting
1600000, false northing 10000000, scale factor 0.9996.
"""
import math

a  = 6378137.0
f  = 1.0 / 298.257222101
b  = a * (1 - f)
e2 = f * (2 - f)
lam0 = math.radians(173.0)
phi0 = 0.0
N0 = 10000000.0
E0 = 1600000.0
k0 = 0.9996

A0 = 1 - e2/4 - 3*e2**2/64 - 5*e2**3/256
A2 = (3.0/8.0) * (e2 + e2**2/4 + 15*e2**3/128)
A4 = (15.0/256.0) * (e2**2 + 3*e2**3/4)
A6 = 35*e2**3/3072

def meridian_arc(phi):
    return a * (A0*phi - A2*math.sin(2*phi) + A4*math.sin(4*phi) - A6*math.sin(6*phi))

def nztm_to_wgs84(E, N):
    Nprime = N - N0
    mprime = meridian_arc(phi0) + Nprime / k0
    n  = (a - b) / (a + b)
    G  = a * (1 - n) * (1 - n*n) * (1 + 9*n*n/4 + 225*n**4/64) * math.pi/180.0
    sigma = mprime * math.pi / (180.0 * G)
    phiprime = (sigma
                + (3*n/2 - 27*n**3/32) * math.sin(2*sigma)
                + (21*n*n/16 - 55*n**4/32) * math.sin(4*sigma)
                + (151*n**3/96) * math.sin(6*sigma)
                + (1097*n**4/512) * math.sin(8*sigma))

    sp, cp = math.sin(phiprime), math.cos(phiprime)
    tp = sp / cp
    rho = a * (1 - e2) / (1 - e2*sp*sp)**1.5
    nu  = a / math.sqrt(1 - e2*sp*sp)
    psi = nu / rho
    t2, t4, t6 = tp**2, tp**4, tp**6
    x  = (E - E0) / (k0 * nu)
    x2 = x*x

    term1 = tp / (k0*rho) * (x*(E - E0)/2.0)
    term2 = tp / (k0*rho) * ((E - E0)*x**3/24.0) * (-4*psi*psi + 9*psi*(1 - t2) + 12*t2)
    term3 = tp / (k0*rho) * ((E - E0)*x**5/720.0) * (
        8*psi**4*(11 - 24*t2) - 12*psi**3*(21 - 71*t2)
        + 15*psi*psi*(15 - 98*t2 + 15*t4) + 180*psi*(5*t2 - 3*t4) + 360*t4)
    term4 = tp / (k0*rho) * ((E - E0)*x**7/40320.0) * (1385 + 3633*t2 + 4095*t4 + 1575*t6)
    phi = phiprime - term1 + term2 - term3 + term4

    secphi = 1.0 / cp
    l1 = x * secphi
    l2 = (x**3 * secphi / 6.0) * (psi + 2*t2)
    l3 = (x**5 * secphi / 120.0) * (-4*psi**3*(1 - 6*t2) + psi*psi*(9 - 68*t2)
                                    + 72*psi*t2 + 24*t4)
    l4 = (x**7 * secphi / 5040.0) * (61 + 662*t2 + 1320*t4 + 720*t6)
    lam = lam0 + l1 - l2 + l3 - l4

    return math.degrees(phi), math.degrees(lam)

if __name__ == "__main__":
    # Validated by nztm_validate.py: 1.5mm worst round trip across NZ, and 1143 of
    # 1147 DOC region labels land inside their region. Do not add recalled LINZ
    # test vectors here; three of four written from memory were wrong and the
    # disagreement looked like a projection bug for a while.
    print(nztm_to_wgs84(1576041.15, 6188574.24))

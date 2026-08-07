---
source: "https://arxiv.org/abs/2506.13724"
type: "arxiv"
canonical_id: "2506.13724"
title: "Logical qubits with erasure conversion using metastable neutral atoms"
authors: "Zhang, Bichen, Liu, Genyue, Bornet, Guillaume, Horvath, Sebastian P., Peng, Pai, Ma, Shuo, Huang, Shilin, Puri, Shruti, Thompson, Jeff D."
year: "2025"
venue: "Nature Physics"
arxiv_id: "2506.13724"
doi: "10.1038/s41567-026-03309-0"
full_text: yes
---

# Logical qubits with erasure conversion using metastable neutral atoms

**Authors:** Zhang, Bichen, Liu, Genyue, Bornet, Guillaume, Horvath, Sebastian P., Peng, Pai, Ma, Shuo, Huang, Shilin, Puri, Shruti, Thompson, Jeff D.

**Citation:** Nature Physics, vol. 22, pp. 910 - 916, 2025

**arXiv:** [2506.13724](https://arxiv.org/abs/2506.13724)

**DOI:** [10.1038/s41567-026-03309-0](https://doi.org/10.1038/s41567-026-03309-0)

## Abstract

Implementing large-scale quantum algorithms with practical advantage will require fault tolerance achieved through quantum error correction, but the associated overhead is prohibitive. This overhead can be reduced by engineering physical qubits with fewer errors, and by shaping the residual errors to be more easily correctable. In this work, we demonstrate quantum error-correcting codes and logical qubit circuits in a metastable ytterbium-171 nuclear spin qubit with a noise bias towards erasure errors. These errors can be located separately from any syndrome information diagnosing the error, and we demonstrate adaptive circuit execution based on erasure information. We show that dephasing errors on the qubit during coherent transport can be strongly suppressed, and implement entangling gates that maintain a high fidelity in the presence of gate-beam inhomogeneity or pointing errors. Furthermore, we demonstrate logical qubit encoding in the [[4, 2, 2]] code, with error correction during decoding based on mid-circuit erasure measurements despite the fact that the code is too small to correct any Pauli errors. Finally, we demonstrate logical qubit teleportation between multiple code blocks with conditionally selected ancillas based on mid-circuit erasure checks, a key part of leakage-robust error correction schemes using neutral atoms. Qubits with detectable erasure errors can support more efficient error correction than qubits with unlocated errors. Improved logical qubit performance using erasure conversion has now been demonstrated using ytterbium-171 atoms.

## Full Text

# **Leveraging erasure errors in logical qubits with metastable**<sup>171</sup> **Yb atoms** 

Bichen Zhang,<sup>1,</sup><sup>_∗_</sup> Genyue Liu,<sup>1,</sup><sup>_∗_</sup> Guillaume Bornet,<sup>1</sup> Sebastian P. Horvath,<sup>1</sup> Pai Peng,<sup>1,</sup><sup>_†_</sup> Shuo Ma,<sup>2,</sup><sup>_‡_</sup> Shilin Huang,<sup>3,</sup><sup>_§_</sup> Shruti Puri,<sup>3</sup> and Jeff D. Thompson<sup>1,</sup><sup>_¶_</sup> 

> 1 _Department of Electrical and Computer Engineering, Princeton University, Princeton, NJ 08544, USA_ 

> 2 _Department of Physics, Princeton University, Princeton, NJ 08544, USA_ 

> 3 _Department of Applied Physics, Yale University, New Haven, CT 06520, USA_ 

Implementing large-scale quantum algorithms with practical advantage will require fault-tolerance achieved through quantum error correction, but the associated overhead is a significant cost. The overhead can be reduced by engineering physical qubits with fewer errors, and by shaping the residual errors to be more easily correctable. In this work, we demonstrate quantum error correcting codes and logical qubit circuits in a metastable<sup>171</sup> Yb qubit with a noise bias towards erasure errors, that is, errors whose location can be detected separate from any syndrome information. We show that dephasing errors on the nuclear spin qubit during coherent transport can be strongly suppressed, and implement robust entangling gates that maintain a high fidelity in the presence of gate beam inhomogeneity or pointing error. We demonstrate logical qubit encoding in the [[4 _,_ 2 _,_ 2]] code, with error correction during decoding based on mid-circuit erasure measurements despite the fact that the code is too small to correct any Pauli errors. Finally, we demonstrate logical qubit teleportation between multiple code blocks with conditionally selected ancillas based on mid-circuit erasure checks, which is a key ingredient for leakage-robust error correction with neutral atoms. 

Recent advances in scaling quantum processors have led to breakthrough demonstrations of quantum error correction (QEC) and fault-tolerant computing in many hardware platforms [1–7]. At the same time, advances in the design of quantum error correcting codes and fault-tolerant circuits [8–10] and quantum algorithms [11–13] has reduced the apparent computational cost of running large-scale algorithms for real-world applications. Nevertheless, there is a significant gap between the projected requirements and the capabilities of current hardware, which has motivated efforts to improve physical qubit performance and scale. 

A complementary approach to reducing the overhead of fault-tolerant computing is to engineer qubits such that the inevitable errors are of a type that can be efficiently corrected. Qubits with biased Pauli noise can be used to raise the threshold and lower the overhead [14, 15], motivating recent studies of bosonic qubits [16–18]. Another approach is to engineer qubits with predominantly erasure errors [19, 20] by shaping the physical errors into detectable leakage outside of the computational subspace [21–23]. This can lead to significantly higher thresholds and improved sub-threshold scaling [22–25], and has motivated experimental work in a number of platforms [26–31]. 

In this work, we demonstrate QEC primitives using qubits encoded in the metastable<sup>3</sup> P0 state of<sup>171</sup> Yb, which allows fast detection of certain errors as erasures with very little backaction onto qubits remaining in the computational space [22, 26]. The execution of programmable circuits is facilitated by a zone-based architecture [4], and we demonstrate several unique capabilities of<sup>171</sup> Yb in this context. First, decoherence during moving is strongly suppressed by using the nuclear spin qubit and with appropriate control of the dipole trap polarization, leaving an error channel that is strongly biased towards loss. Second, single-photon Rydberg excitation enables two-qubit gates that are robust to intensity variations across the gate zone [32, 33]. We leverage these abilities to demonstrate logical qubit encoding in [[4 _,_ 2 _,_ 2]] codes, and show improvement in the logical qubit decoding by using mid-circuit erasure information. In addition, we demonstrate teleportation of logical qubits between distinct code blocks using conditionally selected ancillas based on mid-circuit erasure checks, which is a key building block for leakage- and loss-robust error correction protocols. 

We implement programmable quantum circuits by transporting atoms between a storage zone and a gate zone (Fig. 1a) [4, 6]. The static traps defining both the storage and gate zones are generated by a liquid crystal spatial light modulator (SLM), while the dynamic transport traps that govern the circuit execution are generated by a pair of orthogonally oriented acousto-optic deflectors (AODs). The AODs are driven by piecewise-polynomial waveforms generated in real-time using a field-programmable gate array (FPGA) [38], configured to receive mid-circuit erasure check information from a fast EMCCD camera through an intermediate computer. The gate zone is illuminated by a 

> _∗_ These authors contributed equally to this work. 

> _†_ Present address: School of Physics, Peking University, Beijing 100871, China. 

> _‡_ Present address: Department of Physics, University of California, Berkeley, CA 94720, USA. 

> _§_ Present address: Department of Physics, The Hong Kong University of Science and Technology, Clear Water Bay, Kowloon, Hong Kong, China. 

> _¶_ jdthompson@princeton.edu 

2 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-01.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-02.png)


<!-- Start of picture text -->
ν =54.3<br>F=1/2<br>Ωr<br>3P0<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-03.png)


<!-- Start of picture text -->
gates<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-04.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-05.png)


<!-- Start of picture text -->
1P1<br>1S0<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-06.png)


<!-- Start of picture text -->
B 0<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-07.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-08.png)


<!-- Start of picture text -->
Erasure conversion<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-09.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-10.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-11.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-12.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-13.png)


<!-- Start of picture text -->
1.00<br>0.75<br>θ<br>0.50<br>0.25<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-14.png)


<!-- Start of picture text -->
E<br>trap<br>B<br>trap<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-15.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-16.png)


<!-- Start of picture text -->
B trap ∥ B 0<br>B trap ⟂ B 0<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-17.png)


<!-- Start of picture text -->
B SLM ∥ B AOD ⟂ B 0<br>B AOD ⟂ B SLM ∥ B 0<br>Stationary<br><!-- End of picture text -->


![](.figures/arxiv__2506.13724/2506.13724.pdf-0002-18.png)


<!-- Start of picture text -->
Conditioned<br>Raw<br><!-- End of picture text -->

Figure 1. **Logical qubit architecture and coherent transport with metastable**<sup>171</sup> **Yb qubits.** (a) Schematic of storage and gate zones for implementing the [[4,2,2]] code. Qubits are encoded in the nuclear spin sublevels of the metastable<sup>3</sup> _P_ 0 manifold, and leakage errors to the<sup>1</sup> _S_ 0 ground state can be detected using fast imaging on the<sup>1</sup> _P_ 1 transition. Coherent atom transport between the two zones is implemented using AODs controlled by an FPGA, which allows the circuit execution to be adapted based on mid-circuit erasure information. A tightly focused Rydberg laser (302 nm wavelength, 12 _µ_ m 1 _/e_<sup>2</sup> radius) defines the gate zone used to implement both one- and two-qubit gates. Two-qubit gates use resonant excitation from _|_ 1 _⟩_ to the Rydberg state _|r⟩_ = _|_ 6 _sνs, ν_ = 54 _._ 3 _, F_ = 1 _/_ 2 _, mF_ = _−_ 1 _/_ 2 _⟩_ . (b) Selectively applied single-qubit gate _Rz_ ( _θ_ ) applied in the gate zone (purple), while the atoms in storage zone remain unaffected (gray). (c) The metastable qubit experiences a vector light shift near the tweezer focus that induces a synthetic magnetic field of approximately 50 mG, oriented in the focal plane, perpendicular to the tweezer polarization. (d) Coherence measured with a Ramsey sequence in stationary tweezers with the synthetic field perpendicular to the bias field ( _T_ 2<sup>_∗_= 0</sup><sup>_._45(2)s)orparalleltoit(</sup><sup>_T_</sup> 2<sup>_∗_= 0</sup><sup>_._39(1)s).(e)Coherencemeasuredwith</sup> a Ramsey sequence while transporting atoms between the storage and gate zones when the synthetic field of the SLM tweezers is parallel (green) or perpendicular (blue) to the external field, compared to an atom held in a stationary tweezer for the same duration (orange). A one-way trip includes handing off atoms from the SLM to AOD tweezers and back. (f) Atom loss from the metastable state while transporting between the storage and gate zones, before (green) and after (blue) conditioning on the absence of a mid-circuit erasure detection. The expected scattering contribution is shown in orange. Approximately half of the loss is detectable over the first three round trips. The small markers show the loss from individual traps, while the large markers show the average across the array. 

focused 302 nm laser beam used to implement entangling Rydberg gates via the _|ν_ = 54 _._ 3 _⟩_ state (Fig. 1a; _P_ = 20 mW, Ω _r_ = 2 _π ×_ 2 _._ 5 MHz) [39]. For convenience, we also use the Rydberg transition to implement selective single-qubit _Z_ ( _θ_ ) rotations, which are complemented by a global radio-frequency drive to provide full single-qubit control (Fig. 1b). 

Minimizing qubit errors during transport is critical in a reconfigurable processor. Implementations with alkali atoms make use of rapid dynamical decoupling interleaved with the atomic motion to suppress errors from differential light shifts [40–42]. Rapid dynamical decoupling is challenging with the nuclear spin qubit in Yb, however, seconds-scale coherence times can be achieved without it in both the<sup>1</sup> S0 and<sup>3</sup> P0 states [26, 43–46]. Compared to the<sup>1</sup> S0 ground state, the<sup>3</sup> P0 state has a much larger vector light shift from elliptical polarization [47]. The tweezer light is elliptically polarized near the focus from non-paraxial effects [48], which generates a synthetic field varying across the tweezer with maximal magnitude _|⃗B_ trap _|_ = 50 mG at a typical trap depth (Fig. 1a). This can split the qubit levels by ∆ _ν_ = 57 Hz if the external bias field _⃗B_ 0 is parallel to _⃗B_ trap; the effect can be reduced by applying the bias field in the perpendicular direction (here, _|⃗B_ 0 _|_ = 5 G suppresses ∆ _ν_ to 0 _._ 3 Hz). Either configuration is sufficient to achieve long coherence times in stationary traps, where the atomic motion is centered on the focus (Fig. 1d). However, we observe strong dephasing when handing off atoms between traps with opposite polarization (green curve in Fig. 1e), as the potential minimum is displaced from the beam focus during the handoff. 

With the optimal polarization configuration ( _⃗B_ SLM _∥⃗B_ AOD _⊥⃗B_ 0), we observe a combined dephasing and bit flip error probability of _<_ 6 _×_ 10<sup>_−_4</sup> (Fig. 1e) per one-way trip from the storage zone to the gate zone, measured by the 

3 








![](.figures/arxiv__2506.13724/2506.13724.pdf-0003-04.png)


<!-- Start of picture text -->
a b 0.25 1.0 c<br>0.00<br>−0.25<br>0.5<br>−0.50<br>−0.75<br>0.0<br>0.0 0.5 1.0<br>Time [ μ s]<br>d 1.0 e f 1.00<br>0.9<br>0.8<br>0.95<br>0.6 0.8<br>0.90<br>0.4<br>0.7<br>0.85 AR<br>0.2<br>TO<br>0.6<br>0.0 0.80<br>−10 0 10 0 10 20 −40% −20% 0<br>Detuning [MHz] Circuit depth,  d Laser intensity error,  Δ I / I<br>] π  [a.u.]<br>ϕ )(  [ t 2)||Ω( t<br>Phase,<br>Intensity,<br>|00⟩<br>P<br> population<br>0<br>P<br>3 CZ gate fidelity<br><!-- End of picture text -->

Figure 2. **Amplitude-robust CZ gates.** (a) The AR gate is a symmetric CZ gate that uses a phase-modulated drive to implement simultaneous closed trajectories when starting from _|_ 01 _⟩_ (or _|_ 10 _⟩_ ) and _|_ 11 _⟩_ , leveraging the _~~√~~_ 2 enhancement of the Rabi frequency from the blockaded excitation to _|rr⟩_ in the latter case to implement an entangling gate [34, 35]. (b) AR gate intensity (red) and phase (blue) profiles, measured with a heterodyne interferometer [26]. The ideal waveforms are shown with solid lines. (c) Bloch sphere trajectories during the AR gate in the _{|_ 01 _⟩ , |_ 0 _r⟩}_ subspace (orange) and _{|_ 11 _⟩ , |W ⟩}_ subspace (grey). (d) Measurement of the _|_ 1 _⟩_ – _|r⟩_ transition at different laser powers ranging from Ω _r/_ (2 _π_ ) = 0 _._ 5 MHz to 2 _._ 5 MHz. No shift is observed, bounding the light shift coefficient to _χ <_ 3 kHz/MHz<sup>2</sup> . (e) Randomized circuit benchmarking [26, 36, 37] of AR gates with mid-circuit erasure detection. The extracted error rate of the AR CZ gate is _ϵ_ AR = 0 _._ 016(1) (solid blue), which is reduced to _ϵc,_ AR = 0 _._ 011(1) (solid green) after conditioning on not detecting an atom in the ground state before the end of the circuit. Under the same conditions, the TO gate errors (light curves) are _ϵ_ TO = 0 _._ 011(1) and _ϵc,_ TO = 0 _._ 006(1). (f) CZ gate fidelity as a function of the deviation of the intensity from the nominal calibration point, ∆ _I/I_ . The solid curves show phenomenological fits to (∆ _I/I_ )<sup>2</sup> and (∆ _I/I_ )<sup>4</sup> for the TO and AR data, respectively. 

Ramsey fringe contrast of surviving atoms. A one-way trip lasts approximately 2.5 ms and includes handing off atoms between the stationary and moving tweezers on each side, without any dynamical decoupling. The error per trip is determined by repeating up to 12 trips. Photon scattering (Raman scattering and photoionization [26]) and heating contribute additional errors in the form of leakage from<sup>3</sup> P0 and atom loss. Over the first round trip (comprising four trap handoffs and two shuttling steps), the average loss probability from<sup>3</sup> P0 is 1.1(4)% (Fig. 1f), which increases in subsequent trips because the atom is heated. Before the onset of heating, roughly half of this loss is detectable mid-circuit as an erasure error. 

Next, we turn to two-qubit gates. A common challenge to laser-driven gates is laser intensity variations, which can arise from laser noise, pointing instability or inhomogeneity across a gate zone, and our day-to-day gate fidelity is limited by pointing stability of the Rydberg gate laser. To circumvent this challenge, we implement a variant of the usual symmetric CZ gate [34, 35] that is robust against quasi-static laser intensity variations, called the amplituderobust (AR) gate (Fig. 2a – c) [32, 33]. For a fractional intensity error ∆ _I/I_ , the AR gate error scales as _ϵ ∝_ (∆ _I/I_ )<sup>4</sup> instead of (∆ _I/I_ )<sup>2</sup> for conventional gates, at the expense of spending 60% more time in the Rydberg state. The AR gate requires that the AC Stark shift of the Rydberg transition ∆ _LS_ = _χ_ Ω<sup>2</sup> _r_<sup>issmallerthantheRabifrequency[32],</sup> which we show is easily satisfied for single-photon gates in<sup>171</sup> Yb (Fig. 2d). The AR gate fidelity at the typical laser power is _F_ AR = 0 _._ 984(1), which is 1.45 times more error than the time-optimal (TO) gate fidelity of _F_ TO = 0 _._ 989(1) under the same conditions (Fig. 2e). Remarkably, the AR gate fidelity is nearly unchanged when deliberately reducing the gate laser intensity by a significant amount without recalibration (Fig. 2f). Roughly 31% of the AR gate error is detected mid-circuit as erasure errors (Fig. 2e). 

We now proceed to study erasure conversion in the context of the [[4 _,_ 2 _,_ 2]] error detecting code. As a _d_ = 2 code it is typically used for error detection [3, 49, 50], but it can also correct a single erasure error. The codespace is stabilized by _SZ_ = _Z_<sup>_⊗_4</sup> and _SX_ = _X_<sup>_⊗_4</sup> , and the logical operators are given by _XL_<sup>(1)</sup> = _X_ 1 _X_ 3 and _XL_<sup>(2)</sup> = _X_ 1 _X_ 2, and _ZL_<sup>(1)</sup> = _Z_ 1 _Z_ 2 and _ZL_<sup>(2)</sup> = _Z_ 1 _Z_ 3 (Fig. 3a) [19]. The encoding circuit in Fig. 3b is used to prepare the _|_ 00 _⟩L_ or 

4 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0004-01.png)


<!-- Start of picture text -->
a b Logical state preparation Hold Z/X-basis<br>1 t measurement<br>Z1 Z2<br>2 SZ 3 1<br>4 2<br>1 3<br>X2 X1<br>2 SX 3 4<br>4<br>c 1.00 e 1.0<br>0.95<br>0.90 0.9<br>0.85<br>0.80<br>0.8<br>d 0.8<br>0.6<br>0.4 0.7 w/o erasure<br>0.2 w/ erasure<br>0.0<br>0.0 0.1 0.2 0.3 0.4 0.5 0.0 0.1 0.2 0.3 0.4 0.5<br>Wait time,  t  [s] Wait time,  t  [s]<br>Postselected success rate<br>Success rate<br>Accept rate<br><!-- End of picture text -->

Figure 3. [[4 _,_ 2 _,_ 2]] **code implementation.** (a) Stabilizers and logical operators of the [[4 _,_ 2 _,_ 2]] code. (b) Encoding circuit for _|_ 00 _⟩L_ and _|_ ++ _⟩L_ . The latter is obtained by applying transversal _Ry_ ( _π/_ 2) gates to the four data qubits (green box). After a waiting period _t_ , an erasure check (blue) is followed by transversal measurements on all qubits and decoding of the logical state in the _Z_ or the _X_ basis. A flag qubit is used to catch certain high-weight Pauli and leakage errors. (c) Post-selected state preparation and memory fidelity after preparing _|_ 00 _⟩L_ (round markers) or _|_ ++ _⟩L_ (square markers), shown alongside simulation results (solid and dashed curves). Green data corresponds to post-selection on the measured parity (i.e., stabilizer value) alone; orange includes both parity and flag qubit detection in the bright state ( _|_ 0 _⟩_ ); blue further conditions on the absence of detected erasure errors. The success probability describes the probability to decode a single logical qubit correctly. (d) Acceptance rates corresponding to the different post-selection choices used in (c). (e) State preparation and memory fidelities without postselection for _|_ 00 _⟩L_ (circles) and _|_ ++ _⟩L_ (squares), shown alongside simulation results. The green data corresponds to decoding only using the qubit measurement data, while the blue data incorporates the erasure information. The gray diamonds show the preparation and memory fidelity of a single physical qubit. 

_|_ ++ _⟩L_ state, with an ancilla flag that can be used to detect certain high weight Pauli and leakage errors (see SI Sec. I G). After a variable hold time _t_ , we perform a mid-circuit erasure check to detect any erasure errors during the preparation circuit or idle time, then make a final transversal measurement of all qubits and decode. 

When using the code for error detection without erasure information, we achieve a logical qubit state preparation fidelity averaged over _|_ 00 _⟩L_ and _|_ ++ _⟩L_ of 0.981(2), which increases to 0.990(1) when also post-selecting on the flag qubit (Fig. 3c). Additionally post-selecting on the mid-circuit erasure information improves the initialization to 0.995(1). The post-selected error rate grows quadratically with time during the hold period in all cases, but the rate is 3.6(1) times slower when including the erasure information. The data is in good agreement with a simulation based on independently measured errors (see SI Sec. I H). 

Importantly, mid-circuit erasure information can be used to improve the unconditional decoding of the _d_ = 2 code, increasing the probability to decode the correct logical state without post-selection (Fig. 3e). The state preparation fidelity increases from 0.874(4) to 0.902(3) when erasure information is included, and the decay rate with increasing hold time is reduced by a factor of 1.9(4). For this code, the decoding rule with erasure information is simple: if the parity is even, no correction is applied; if the parity is odd and exactly one erasure is present, we flip the erased qubit. 

Finally, we demonstrate teleportation of logical qubits, an important QEC primitive for error correction in the presence of atom loss. In this experiment, two pairs of logical ancilla qubits are prepared in Bell states, and the logical data qubits are teleported using a circuit equivalent to Knill’s teleportation circuit [51] (Fig. 4a). When post-selecting on trivial syndrome values in all logical qubits and the absence of flags, the teleportation fidelity is 0.771(9), averaged over the _|_ 00 _⟩L_ and _|_ ++ _⟩L_ input states (Fig. 4b). It rises to 0.87(2) when also post-selecting on the absence of erasures. Without any post-selection, the teleportation fidelity when decoding using erasure information is _F_ = 0 _._ 588(3), limited by uncorrectable Pauli errors in the _d_ = 2 code. 

5 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0005-01.png)


<!-- Start of picture text -->
a b 1.0 c<br>0.82 Parity & flag<br>0.8<br>0.80<br>0.6 0.78<br>0.4 0.76<br>Z/X-basis measurement<br>0.2 0.74<br>with feedforward<br>0.0 0.72<br>Parity Parity & Parity &<br>Erasure detection CPU FPGA flag flag & 0.70<br>erasure Random Adaptive<br>Postselected success rate<br>Postselected success rate<br><!-- End of picture text -->

Figure 4. **Logical qubit teleportation with adaptive ancilla selection.** (a) After state preparation, a mid-circuit erasure check is used to select two ancillas without erasure errors to prepare a logical Bell state. The input logical state is teleported to the second ancilla block and decoded in the Z or X basis. (b) Teleportation success probability when post-selecting the final parity of all logical qubits, parity and flag, or further the absence of detected erasure errors, averaged over teleporting _|_ 00 _⟩L_ and _|_ + + _⟩L_ . Here, randomly selected logical ancillas are used to form the Bell pair. (c) Teleportation success probability with adaptively selected logical ancilla qubits. A comparison of the post-selected success rates per logical qubit of decoding _|_ 00 _⟩L_ between random and adaptive selection of ancilla blocks. 

When erasures are detected in the preparation of the ancilla qubits, the affected logical blocks can be discarded instead of attempting to repair the errors. We demonstrate this using adaptive control over the atom trajectories to select two out of the four ancilla blocks without a detected erasure. We observe a modest improvement in the teleportation fidelity, from 0.771(9) to 0.802(8), with post-selection on both trivial syndrome values and the flag qubit. This limited gain reflects the fact that logical errors are primarily dominated by Pauli errors rather than erasures in our current system. However, the use of post-selected resource states is expected to yield significantly higher thresholds when erasure errors are dominant [25, 52, 53]. 

In this work, we have demonstrated a zoned architecture for metastable<sup>171</sup> Yb qubits leveraging mid-circuit erasure error detection, low-decoherence atom transport and robust entangling gates. We implemented several QEC primitives with erasure conversion, including error correction during decoding using an error-detecting code and logical state teleportation between code blocks. 

In this circuit implementation with a 1D gate zone, transport errors dominate the error budget. The five CZ gates in the encoding circuit are implemented sequentially in a manner that requires two moves from the storage to the gate zone and four trap handoffs, for a total depth of 8 long-distance moves and 16 handoffs, and a similar number are used in the readout step. The temporal overhead (29 ms) results in a decay probability from<sup>3</sup> P0 of 1.8% per qubit over the entire circuit, in addition to the 2.6% loss from active moving. In the future, using a 2D gate zone and separate trap arrays for data qubits and ancillas will allow a single surface syndrome extraction cycle to be implemented with no handoffs and four short-distance moves [41], requiring less than 1 ms and a<sup>3</sup> P0 decay probability below 0.1%. To achieve _F_ = 0 _._ 999 across a _d_ = 5 surface code spanning 50 _µ_ m, a Rydberg laser with a power of 2.3 W in Gaussian profile of 10 _×_ 110 _µ_ m<sup>2</sup> is sufficient [39], leveraging the AR gate to use a beam waist that is comparable to the array size. To cover a larger array without further increasing the Rydberg laser power, the gate beam could be scanned through several discrete positions, using local light shifts to turn off gates for atoms near the border between positions [54, 55]. 

While this work demonstrates that erasure information can be used to improve logical qubit performance, repeated error correction and deep logical circuits will require replacing the affected atoms, as well as atoms that were lost without being detected, using leakage reduction units [56]. The most natural approach for neutral atoms is to teleport logical information to freshly prepared physical qubit arrays, as considered by Knill [51] and in measurement-based quantum computing implementations [25, 52]. It has recently been proposed that loss-resolving measurements [46, 57– 59] can provide erasure-like information about qubit loss [60–64]. This can result in improved erasure detection performance: for example, we have measured that 75% of the TO gate errors in Fig. 2e result in atom loss, and virtually all of the transport errors are loss. To ensure a supply of new physical qubits, a key step for the future of this platform will be fast mid-circuit atom replacement to allow loss errors to be replenished [59, 65, 66]. 

_Note_ While completing this work, we became aware of complementary work on<sup>171</sup> Yb, demonstrating metastable qubit gates with atom loss detection [67]. 

We acknowledge the QICK team at Fermilab (Gustavo Cancelo, Leandro Stefanazzi) for developing the FPGA tweezer controller, and Sara Sussman for the help with the initial implementation. We also thank Sven Jandura, Andrew Ludlow, Kyle Beloy and Adam Kaufman for helpful conversations. This work was supported by the Army Research Office (W911NF-18-10215, W911NF-24-10358), DARPA MeasQuIT (HR00112490363) and ONISQ (W911NF20-10021), the Office of Naval Research (N00014-23-1-2621), and the National Science Foundation through the CA- 

6 

REER program (PHY-2047620) and the Center for Robust Quantum Simulation (OMA-2120757). **Competing interests** S.P.H and J.D.T are co-founders and shareholders of Logiqal, Inc. 

7 

## **I. SUPPLEMENTARY INFORMATION** 

## **A. Experimental implementation** 

Our apparatus has a static and a dynamic optical tweezer array. The static path is generated by a spatial light modulator (SLM, Hamamatsu model X13138-04WR) and has 88 traps: 3 _×_ 26 traps for storage and loading, and 10 in the gate zone. The dynamic path is generated by a pair of orthogonal acousto-optic deflectors (AODs). Both optical paths are derived from the same laser source (Coherent Genesis CX-488) at a wavelength of _λ_ = 487 nm with opposite AOM frequency shifts to avoid interference. For most experiments, the two paths have orthogonal linear polarizations and are combined via a polarizing beamsplitter. 

171 The physical qubits are encoded in the metastable 6 _s_ 6 _p_<sup>3</sup> P0 states of neutral Yb, where _|_ 0 _⟩ ≡ |F_ = 1 _/_ 2 _, mF_ = _−_ 1 _/_ 2 _⟩_ and _|_ 1 _⟩≡|F_ = 1 _/_ 2 _, mF_ = 1 _/_ 2 _⟩_ . The metastable state is initialized and measured using optical pumping, following the procedure in Ref. [26]. We have improved the efficiency of the pumping process by applying the pumping while modulating the optical dipole trap (see Sec. I E), which eliminates light shifts during the pumping processes. With this approach, we observe a round-trip pumping loss of 0.6%. We believe the majority of the losses arise in the depumping step. 

The lifetime of the metastable state is measured to be 1 _._ 64(3) s, under a trap power of approximately 1 _._ 5 mW per tweezer and is primarily limited by the Raman scattering and photoionization from the trap light. The spin-flip time _T_ 1 exceeds 13 s, and the coherence time is measured to be _T_ 2<sup>_∗_= 0</sup><sup>_._39(1)s(with</sup><sup>_T_2= 6(2)s).</sup> 

Global single-qubit gates are driven by a radio-frequency (RF) magnetic field. Under our applied bias magnetic field of _B_ 0 = 5 G, the Larmor frequency between _|_ 0 _⟩_ and _|_ 1 _⟩_ is _ωL_ = 2 _π ×_ 5 _._ 7 kHz. To operate within the rotating-wave approximation regime, we employ a relatively low Rabi frequency of ΩSQ _∼_ 2 _π ×_ 200 Hz, but this restriction is not fundamental [68]. We measure a fidelity of _F_ 1Q = 0 _._ 9990(1) for RF single-qubit gates using randomized benchmarking. 

A focused 302 nm laser (1 _/e_<sup>2</sup> radius _w_ 0 = 12 _µ_ m) defines the gate zone for performing two-qubit gates [4, 41]. For convenience, we implement selective single-qubit gates using the same beam, performing _Z_ rotations via the Rydberg state. Selective projective measurements are also implemented in this zone by blowing out population in the _|_ 1 _⟩_ state through excitation to the Rydberg state and subsequent autoionization [26, 43], though the population remaining in _|_ 0 _⟩_ is not imaged until the end of the circuit. 

Following Ref. [26], two different cycling transitions are used to measure information about the qubits. For initialization and final measurement, we use the intercombination line<sup>1</sup> S0 _→_<sup>3</sup> P1 at 556 nm, achieving a fidelity and survival probability of 0.995 with a 15 ms exposure time. For the mid-circuit erasure detection, we use the<sup>1</sup> S0 _→_ 1 P1 transition at 399 nm, achieving a detection fidelity of _≈_ 0 _._ 99 in 20 _µ_ s at the expense of heating the atom out of the optical dipole trap. Because of the short exposure time and large detuning, the erasure detection has negligible back action on qubits remaining in the metastable state. 

## **B. Real-time AOD waveform generation** 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0007-10.png)


<!-- Start of picture text -->
FPGA<br>32x<br>TTL Memory FM DDS RF AOD x<br>AM<br>32x<br>FM RF AOD y<br>Polynomial Memory DDS<br>coefficients AM<br>Control<br><!-- End of picture text -->

Figure S1. **Real-time waveform generation** The AOD waveforms are generated on a Xilinx RFSoC ZCU216 evaluation board. The trajectories are expressed as piecewise polynomial coefficients in frequency and amplitude. The coefficients are transmitted to the FPGA over ethernet, and the execution of each segment is triggered by a TTL line. Two output channels drive orthogonally oriented AODs, each supporting up to 32 DDS tones. 

8 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0008-01.png)


<!-- Start of picture text -->
a b 1.0 c 5<br>w/o lensing<br>0.8 w/ lensing 0<br>Experiment<br>0.6 −5<br>Defocus/ 0.4 50<br>Astigmatism<br>0.2<br>0<br>0.0<br>0 100 200 300 0.0 0.5 1.0<br>Moving time,  T  [ μ s] t  [ T ]<br>2 ]<br>T / L<br> [<br>x<br>3 ]<br>Chirping Survival rate T / L<br> [<br>x<br><!-- End of picture text -->

Figure S2. **AOD lensing effect.** (a) Due to the finite shear mode acoustic speed in the AOD crystal and a large optical aperture, a non-negligible lensing effect occurs when chirping the AOD driving frequency, causing defocus and astigmatism. (b) Experimentally measured survival probability (circles) after a single-way between the storage and gate zones while changing moving time _T_ , with the zero-jerk trajectory (blue) and minimum-jerk trajectory (green). Numerical simulation with (solid line) and without (dash line) considering the lensing effect are also shown. The simulation matches with experiment only if the lensing effect is included. (c) Acceleration and jerk profiles of the zero-jerk trajectory (blue) and minimum-jerk trajectory (green). 

The RF for the acousto-optic deflector is generated by a ZCU216 RFSoC FPGA evaluation board programmed with a variant of the QICK firmware [38]. The X/Y channel outputs are generated by summing 32 independent DDS generators (Fig. S1). For each DDS outputs an independent RF tone and can be programmed to perform a frequency chirp described by a piecewise fifth-order polynomial (allowing trajectories such as min-jerk [69] to be specified as a single segment), along with a third-order polynomial for the amplitude. This allows waveform information to be transmitted much more efficiently than a raw waveform [70]. Sequence synchronization is achieved using a real-time processor on the FPGA, which receives streaming commands from a PC with a frame grabber that is used to process the camera images. We currently operate with a 25 ms latency between the end of the image exposure time and the beginning of the next step of waveform generation. Most of this delay is to accommodate worst-case latency depending on other processes running on the PC. The FPGA-generated waveforms are compatible with future developments to lower this latency, or to process images directly on the FPGA. 

## **C. Atom loss and heating during transport** 

During mid-circuit movement, atom transport can introduce heating or even result in atom loss. In our investigation, we identify a few contributing factors in our system. 

Intuitively, transporting atoms too quickly leads to increased heating and atom loss. This behavior is consistent with our experimental observations (Fig. S2b), where we hold atoms in AOD traps and perform a single transport from the storage to the gate zone. To identify the primary limitation in this experiment, we develop a numerical model based on the Monte Carlo method to simulate the classical dynamics of atoms during transport. Interestingly, we find that the dominant limitation is not radial heating from the trap, but rather the “acoustic lensing effect” (Fig. S2a [42, 71]). This effect arises from the finite response time of the AOD: as the driving frequency is swept, the AOD acts like a cylindrical lens, introducing astigmatism in the optical trap. 

The focal shift _δz_ ( _t_ ) induced at the optical trap can be expressed as 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0008-08.png)


where _zR_ and _w_ are the Rayleigh range and beam waist of the optical tweezer in the atomic plane, respectively, while _w_ aod and _vs_ denote the AOD aperture (radius) and the speed of sound in the AOD material, and _τ_ aod = _waod/vs_ is the AOD output rise time. Cylindrical lensing begins to be significant when the transport speed exceeds one beam waist per _τ_ aod, and is therefore more pronounced for shorter trap wavelengths when moving a fixed distance. 

In the experiment, we study this acoustic lensing effect by varying the transport trajectory between the storage and gate zones. As described in Sec. I B, we parameterize the trajectories using a fifth-order polynomial. With additional 

9 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0009-01.png)


<!-- Start of picture text -->
a b c<br>50<br>2.5<br>40 10.0 0.003<br>2.0<br>30 7.5<br>1.5 0.002<br>20 5.0<br>1.0<br>0.001<br>10 2.5<br>0.5<br>0 0.0 0.0 0.000<br>0.0 0.5 1.0 1.5 2.0 2.5 5.0 7.5 0 1 2<br>Time [ms] Trap depth,  V  [MHz] Time [ms]<br>−1 ]<br>m]<br>μ<br> [<br>x<br>Scattering rate [s Total trap depth [MHz] Scattering probability<br><!-- End of picture text -->

Figure S3. **Scattering during atom transport.** (a) Schematic and trajectory of a one-way transport sequence: two hand-off phases between the static and moving optical tweezers (grey shading) bracket a moving phase (white). (b) Measured metastable state scattering rate versus trap depth, together with a quadratic fit [26]. (c) Time trace of the total trap power experienced by the atom during the full trajectory (red); using the model in (b) we infer the cumulative probability of photo-ionization (grey dashed) and the total number of scattered photons (grey solid). 

symmetry constraints, the trajectory takes the form 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0009-04.png)


where _T_ and _L_ are the duration and distance of transport, and _γ_ corresponds to the velocity at _t_ = _T/_ 2 (in unit of _L/T_ ) and can be freely tuned. We compare two specific trajectories: _γ_ = 1 _._ 5625 (we call it _zero-jerk_ trajectory since the jerk vanishes at both the start and end points, see Fig S2c) and _γ_ = 1 _._ 875 (the minimum-jerk trajectory [69]). In both cases, experimental results match the numerical model without any free fitting parameters only when the acoustic lensing effect is included (Fig. S2b). Furthermore, the model predicts that with lensing taken into account, the zero-jerk trajectory outperforms the minimum-jerk one, which we verify experimentally. While in the absence of acoustic lensing, both trajectories perform similarly according to the simulation. We use the zero-jerk trajectory for the circuits in the rest of this work. 

A one-way transport between the gate and storage zone in this work consists of three phases: (1) ramping up the AOD trap depth to handoff qubits from SLM traps to AOD traps, (2) moving, and (3) ramping down the AOD trap depth to handoff qubits back from AOD traps to SLM traps, as shown in Fig. S3a. To mitigate heating accumulated over multiple rounds of transport required by the circuit experiments, we use a longer moving time of 0.89 ms and a ramp time of 0.78 ms. 

Another challenge for atom transport is scattering from the trap light. The<sup>3</sup> P0 metastable state qubits in particular suffer from both off-resonant scattering to other electronic states (such as the ground state) and photoionization [26]. Increasing the AOD trap depth helps minimize heating and enable faster moving (Fig. S3a), at the cost of higher scattering rates (Fig. S3b and c). For the current move parameters, the expected scattering probability is about 0.3% per one-way trip, which is roughly divided into 0.1% per handoff and 0.1% for the move, comparable to the total error rate for these steps quoted in other works [4, 6]. The scattering probability depends strongly on the tweezer wavelength, and photoionization in particular vanishes for wavelengths longer than 604 nm. 

## **D. Decoherence during trap handoff** 

One of the key advantages of using alkaline-earth(-like) atoms in optical tweezer arrays is the ability to encode qubits in nuclear spin states. In both the ground state (<sup>1</sup> S0) and the metastable clock state (<sup>3</sup> P0), the two valence electrons form a closed-shell configuration with total electronic angular momentum _J_ = 0. Consequently, the hyperfine Zeeman sublevels _|mF ⟩_ are predominantly nuclear in character. Unlike hyperfine qubits in alkali atoms, where coherence is often limited by differential scalar light shifts between _|_ 0 _⟩_ and _|_ 1 _⟩_ [72], nuclear spin qubits in these _J_ = 0 states typically exhibit excellent coherence, with _T_ 2<sup>_∗_timescalesontheorderofseconds,asdemonstratedinthisworkand</sup> Ref. [26, 43, 44, 46]. The magnitude of differential light shifts is commonly characterized by the dimensionless parameter _η_ = _δE/V_ , where _δE_ is the energy difference between the two qubit states and _V_ is the average (scalar) trap depth. 

Although our system is free from differential scalar light shifts, they are still susceptible to vector light shifts. While the shift of the<sup>1</sup> S0 ground state is very small, the _|_<sup>3</sup> P0 _, mF_ = _±_ 1 _/_ 2 _⟩_ experience a much larger shift because of 

10 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0010-01.png)


<!-- Start of picture text -->
a AOD b c<br>E AOD 0 50 0.8<br>↓ ↑<br>25<br>0.6<br>0<br>d<br>E SLM −25 0.4<br>0.2<br>−50<br>B0 −75 0.0<br>SLM 0 d −0.5 0.0 0.5 −2.5 0.0 2.5<br>Displacement Displacement,  d  [ μ m] Phase,  ϕ  [rad]<br>d 1.0 1.00<br>0.8<br>0.9<br>0.99<br>0.6<br>0<br>0.8<br>2<br>0.4 4 0.98<br>6<br>0.2 8 0.1<br>10 0.97<br>12<br>0.0<br>0.0<br>- π - π /2 0 π /2 π −5 π /4 - π −3 π /4 π /4 0 π /4 0 5 10<br>ϕ  [rad] ϕ  [rad] number of one way-trip<br>e<br>|0⟩<br> P<br>y shift [Hz]<br>c<br>Energy<br>Survival,<br>Frequen<br>P |0⟩ P |0⟩ C / A<br><!-- End of picture text -->

Figure S4. **Decoherence during trap handoff.** (a) Schematic of the suboptimal configuration for SLM and AOD trap, with the two traps orthogonally polarized. The atom sees a summed trap potential of the two traps. When two traps are displaced in the _y_ direction, the atom is pulled away from the center of the SLM trap, experiencing an unsuppressed vector light shift. (b) Larmor frequency shift with various displacement _d_ shown in (a). The purple data is experimentally measured via Ramsey experiments, while the orange curve is the theoretical prediction with a single fitting parameter _η_ vls. Based on this measurement, we estimate the _η_ vls = 3 _×_ 10<sup>_−_4</sup> at a wavelength of 487 nm. (c) The Ramsey fringes after a round-trip between the storage and gate zones under _d_ = _−_ 240 nm (red), _d_ = 0 (gray) and _d_ = 240 nm (blue). (d) Measurement of the Ramsey fringes with various number of one-way-trips that the atoms undergo during the Ramsey experiment (same dataset as the blue curve in Fig. 1e). (e) Fitted contrast _A/C_ as a function of the number of one-way-trip. A linear fit gives a spin flip rate of 1(6) _×_ 10<sup>_−_4</sup> per one-way trip. 

hyperfine mixing with nearby excited levels [47]. For our trapping wavelength, the vector light shift induced by fully circularly polarized light is estimated to be _η_ vls _≈_ 3 _×_ 10<sup>_−_4</sup> [73]. 

This vector light shift introduces two primary challenges. First, any residual ellipticity in the trapping light, caused by imperfect polarization control or birefringence, can induce unwanted energy shifts. Second, even with linearly polarized input light, the high numerical aperture (NA) of the tweezer objective generates longitudinal polarization components near the focus, resulting in an overall elliptic polarization. Through the vector light shift, this generates a position-dependent synthetic magnetic field [48]: 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0010-05.png)


where _gm_ = _h ×_ 1 _._ 14 kHz/G characterizes the hyperfine splitting of the two metastable states, and _⃗E_ ( _r_ ) is the oscillating electric field normalized such that _|⃗E|_ = _E_ 0 at the trap center. In the focal plane, _⃗B_ trap is strongest on opposite sides of the tweezer and oriented perpendicular to the polarization direction (main text Fig. 1d). 

Such synthetic magnetic fields have been shown to induce decoherence [48], as spatial gradients in _⃗B_ trap( _r_ ) couple the qubit and motional degrees of freedom. The strength of this coupling depends on the orientation between _⃗B_ trap and the applied bias field _⃗B_ 0. When the tweezer polarization is aligned _parallel_ to _⃗B_ 0, the synthetic field is orthogonal ( _⃗B_ trap _⊥⃗B_ 0), contributing only at second order. In this case, the decoherence is strongly suppressed as long as _|⃗B_ 0 _| ≫|⃗B_ trap _|_ . Conversely, when the tweezer polarization is _perpendicular_ to the bias field, _⃗B_ trap _∥⃗B_ 0, the two fields add directly and modify the effective qubit splitting, resulting in a small differential displacement between the trapping potentials of the two qubit states. This displacement can be expressed as 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0010-08.png)


11 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0011-01.png)


<!-- Start of picture text -->
6<br>a × 10 b Stabilized average 649 nm UV pulses<br>1.5 2 fr 1.5 trap power<br>1.0 1.0<br>... ...<br>0.5 0.5<br>770 nm<br>0.0 0.0<br>0 500 1000<br>fm  [kHz] Time<br> [s]<br>τ<br> lifetime,<br>0 Mod. cycles<br>P<br>3<br><!-- End of picture text -->

Figure S5. **Periodic trap modulation.** (a) Measured lifetime _τ_ of the<sup>3</sup> P0 qubit in an optical trap under different trap modulation frequencies _fm_ (blue dots). Green dots show the corresponding number of modulation cycles _n_ = _τfm_ , which exceeds 10<sup>6</sup> for experimentally realistic _fm_ values. (b) Schematics of synchronizing trap modulation with entangling gates and optical pumping. To switch on (off) trap modulation, we adiabatically ramp down (up) the duty cycle while keep the averaged trap power unchanged. 

where _ω_ is the trap frequency and _m_ is the atomic mass. Notably, this shift _δy_ is only about 30 pm, which is much smaller than the ground-state wavepacket size _σy_ = �ℏ _/_ (2 _mω_ ) = 31 nm, with _δy/σy ∼_ 10<sup>_−_3</sup> . Thus, even in the presence of an unsuppressed synthetic field, static trap-induced dephasing remains negligible. However, when traps are overlapped together, atoms may be pulled away from the center of one trap by another. In this case, if the synthetic fields generated by any trap is parallel to _⃗B_ 0, they will directly shift the energy and the qubit accumulates a phase that depends on the relative alignment of the traps (Fig. S4a). This effect can be harnessed to probe the longitudinal polarization and extract _η_ vls at our tweezer wavelength (Fig. S4b). Moreover, this effect will contribute to decoherence during atom handoffs between traps in the case of SLM and AOD tweezers have orthogonal polarizations, as any misalignment in the direction transverse to _⃗B_ 0 introduces a uncontrolled phase shift during transport. The phase shift is proportional to the displacement, and we measure it be 7 mrad/nm per one-way trip between the storage and gate zones under this configuration (Fig. S4c). Together with the coherence measurement (main text Fig. 1f), we can estimate that we likely have a positional uncertainty of 80 nm when aligning the SLM and AOD traps, combining both the site-to-site difference and fluctuation over time. 

The optimal trap polarization configuration for preserving qubit coherence during transport is to align both the SLM and AOD trap polarizations parallel to the bias magnetic field _⃗B_ 0. To quantify the coherence under this configuration, we perform a Ramsey experiment in which atoms are transported between the storage and gate zones. By measuring the Ramsey contrast as a function of the number of one-way trips, we observe that coherence remains unaffected by the transport, even in the absence of dynamical decoupling. Because atoms experience loss during transport, each Ramsey fringe is fit using a sinusoidal function of the form 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0011-05.png)


where _ϕ_ is the phase of the second _π/_ 2 pulse and _P|_ 0 _⟩_ is the measured survival probability. The coherence is quantified by the normalized contrast _A/C_ . Fitting this value as a function of the number of one-way trips yields an estimated decoherence rate of 1(6) _×_ 10<sup>_−_4</sup> per trip (Fig. S4d and e). 

## **E. Periodic trap modulation** 

To mitigate inhomogeneous light shifts from optical tweezers during operations, the conventional approach is to turn off the trapping light during sensitive procedures such as entangling gate operations or state preparation [26, 36, 37, 41, 74]. However, switching the trap on and off in an irregular manner leads to heating and atom loss, limiting the achievable circuit depth. As an alternative, we employ _periodic trap modulation_ , in which a fixed frequency modulation of the trap is ramped on adiabatically and maintained for the duration of the experiment [75]. Provided the modulation is much faster than the trap frequency, this results in stable micromotion at the modulation frequency but does not heat the atom. 

We experimentally validate this approach using atoms in the<sup>3</sup> P0 state. The trap is modulated with a 50% duty cycle square wave at _fm_ using an AOM, and the lifetime is measured. The average trap depth is stabilized at _V_ avg = _kB ×_ 37 _µ_ K using photodiode feedback through a low-pass filter, corresponding to a trap frequency _fr_ = 30 kHz in the radial direction. The lifetime begins increasing once the modulation frequency is higher than 2 _fr_ , but does not saturate at 

12 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0012-01.png)


<!-- Start of picture text -->
ν =54.3<br>F=1/2<br>3P0<br><!-- End of picture text -->

Figure S6. **Level diagram for the AR CZ gate design.** In our experiment, the Rydberg laser is linearly polarized perpendicular to the quantization axis, resulting in equal _σ_<sup>+</sup> and _σ_<sup>_−_</sup> components. The laser is tuned to the _|_ 1 _⟩_ to _|r⟩_ = _|ν_ = 54 _._ 3 _, F_ = 1 _/_ 2 _, mF_ = _−_ 1 _/_ 2 _⟩_ resonance, but also couples _|_ 0 _⟩_ to _|r_<sup>_′_</sup> _⟩_ = _|ν_ = 54 _._ 3 _, F_ = 1 _/_ 2 _, mF_ = 1 _/_ 2 _⟩_ with a detuning ∆ _r_ from the Zeeman splitting of the Rydberg state. 

the scattering-limited lifetime until nearly 10 _fr_ (Fig. S5a). When measuring the lifetime of the<sup>1</sup> _S_ 0 state in modulated traps (which is not limited by Raman scattering), we have observed lifetimes with large modulation frequencies that significantly exceed the lifetime without modulation, by a factor of 2. A similar effect was observed (but not reported) in Ref. [75], and we do not currently have an explanation. 

For operation of the circuits and benchmarking sequences in this work, we choose a trap modulation frequency of _fm_ = 400 kHz. This trap-off window (1.3 _µ_ s) is sufficient to accommodate our AR CZ gate pulse. The modulation is ramped on (or off) adiabatically over 100 _µ_ s by decreasing (or increasing) the duty cycle, while keeping the total trap power constant. At this modulation frequency, over 600,000 modulation cycles can be applied within the lifetime of the qubit, providing ample opportunity for applying operations. The timing scheme is illustrated in Fig. S5b. 

The periodic trap modulation scheme also improves qubit initialization and readout, both of which rely on the multi-photon optical pumping between the ground state and the metastable state. In particular, population will have to pass through the<sup>3</sup> P2 state, which is anti-trapped at our tweezer wavelength. To prevent atom loss during this step, we synchronize the optical pumping pulses (649 nm pulses, driving the<sup>3</sup> P0 _→_<sup>3</sup> S1 transition) with the trap-off windows, as illustrated in Fig. S5b. This coordination ensures that atoms are never pumped into anti-trapped states while the trap is on, while also avoiding heating that would otherwise result from irregular trap switching. 

## **F. Design of amplitude-robust Controlled-Z gates** 

The AR CZ gate implemented in this experiment is designed using optimal control techniques following Ref. [32]. We extend that work by also considering off-resonant coupling from _|_ 0 _⟩_ to other _mF_ sublevels of the Rydberg state (Fig. S6), and to incorporate the finite bandwidth of the AOM generating the laser pulse. 

Under the assumption of a perfect Rydberg blockade, atom pairs initialized in _|q⟩∈{|_ 00 _⟩ , |_ 01 _⟩ , |_ 11 _⟩}_ evolves disjoint subspaces. The time-dependent Hamiltonian for each initial state is given by: 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0012-09.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0012-10.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0012-11.png)


where we omit _|_ 10 _⟩_ due to its symmetry with _|_ 01 _⟩_ . Here, Ω( _t_ ) and _ϕ_ ( _t_ ) denote the amplitude and phase profiles of the Rydberg laser, respectively, and _ϵ_ represents quasi-static variations in laser intensity that we wish to be robust against. 

For each initial state _|q⟩∈{|_ 00 _⟩ , |_ 01 _⟩ , |_ 11 _⟩}_ , the final state after gate evolution is given by 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0012-14.png)


where _T_ is the gate duration. To realize a CZ gate, we require that the pulse satisfies _|ψq_<sup>(0)</sup><sup>_⟩_=</sup><sup>_eiθq |q⟩_and</sup><sup>_θ_</sup> 11<sup>=</sup> 2 _θ_ 01 _− θ_ 00 + _π_ . By selecting an appropriate amplitude profile Ω( _t_ ) and Zeeman splitting ∆ _r_ , we can design the gate to be amplitude-robust by ensuring that _|ψq⟩_ remains first-order insensitive to _ϵ_ , up to a global phase. This results in: 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0012-16.png)


13 

where _α_ =<sup><u>d</u></sup> d<sup>_<u>θ</u>_</sup><sup><u>00</u></sup> _ϵ_ �� _ϵ_ =0<sup>is a real parameter that can be freely adjusted in GRAPE optimization.We note that since</sup><sup>_θ_00is</sup> non-zero, the amplitude-robust condition is different from one used in Ref. [32], where it simply requires _|ψq_<sup>(1)</sup><sup>_⟩_= 0.</sup> The AR CZ gate is then obtained by minimizing the cost function: 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0013-02.png)


where _F_ represents the fidelity of the CZ gate at _ϵ_ = 0, and _q_ is summed over _{_ 00 _,_ 01 _,_ 11 _}_ . To enable tractable optimization, the phase _ϕ_ ( _t_ ) is approximated as piecewise constant, _ϕn_ , over intervals _t ∈_ [ _nT/N,_ ( _n_ + 1) _T/N_ ) with _N_ = 400. To reduce rapid variations in _ϕ_ ( _t_ ) that may be challenging to implement experimentally, we additionally include a regularization term proportional to<sup>�</sup><sup>_N_</sup> _n_ =0<sup>_−_1(</sup><sup>_ϕn_+1</sup><sup>_−ϕn_)2inthecostfunction</sup><sup>_J_.TheamplitudeprofileΩ(</sup><sup>_t_)</sup> is set to a constant Ω0, with sinusoidal rising and falling edges. The rise (fall) time is chosen to be much longer than 1 _/_ ∆ _r_ to suppress off-resonant oscillations between _|_ 0 _⟩_ and _|r_<sup>_′_</sup> _⟩_ at the beginning (end) of the gate. Although this extends the total gate duration, it does not increase the time atoms spend in the Rydberg state. With the values of ∆ _r/_ Ω0 = 6 _._ 4 and _T_ = 20 _._ 4 _×_ Ω<sup>_−_</sup> 0<sup>1,weobtainanARCZgatewithsimulatedfidelityof1</sup><sup>_−F<_5</sup><sup>_×_10</sup><sup>_−_4inthe</sup> absence of Rydberg decay. 

## **G. QEC circuit implementation** 

The [[4 _,_ 2 _,_ 2]] code is a four-qubit error detection code with stabilizers _X_ 1 _X_ 2 _X_ 3 _X_ 4 and _Z_ 1 _Z_ 2 _Z_ 3 _Z_ 4. The logical states we demonstrate are Greenberger-Horne-Zeilinger(GHZ) states: 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0013-06.png)



![](.figures/arxiv__2506.13724/2506.13724.pdf-0013-07.png)


More details of the code can be found in Ref [19, 49]. 

The encoding circuits for both states are presented in Fig. S7a and b. The state preparation circuit is fault-tolerant to a single physical error (Pauli or atom loss/leakage) when postselecting on a flag qubit. In the absence of errors, the flag qubit is expected to be in the bright state ( _|_ 0 _⟩_ ) at the end of the preparation circuit. The circuit is structured so that any high-weight errors originate only from the flag qubit. Whether the single physical error is of Pauli or leakage type, it results in a dark readout on the flag qubit. 

Fig. S7c shows the circuits for the “encode-hold-decode” experiments. Since the GHZ states are four times more sensitive to dephasing than the physical qubits, a simple Hahn echo is applied to mitigate decoherence during the waiting period. The circuit depicted in the figure represents measurements in the _X_ -basis. By omitting the final _Ry_ � _<u>π</u>_ 2 � _⊗_ 4 gates, measurements in the _Z_ -basis can be performed. Outcomes with either all-dark or all-bright detections in the _Z_ ( _X_ ) basis are decoded as the logical state _|_ 00 _⟩L_ ( _|_ ++ _⟩L_ ). One potential source of overestimating the decoding success rate arises when the atom loss rate is high, as four lost qubits, which appear dark, may be misinterpreted as the correct logical state. To prevent this misinterpretation, we intentionally flip the first and second qubit right before the final transverse measurement and instead expect an outcome of “dark-dark-bright-bright” or “bright-bright-darkdark”. 

The [[4 _,_ 2 _,_ 2]] code teleportation circuit is showed in Fig. S7e. We interleave logical block transportation and two sets of _Rx_ ( _π_ ) gates to cancel out a small magnetic field gradient between the gate and storage zones. 

## **H. Stabilizer circuit simulation with erasure errors** 

We develop a numerical model for simulating the quantum circuits implemented in this work, which is based on the standard stabilizer tableau method, with additional functionality to track qubits that experience leakage or erasure errors. Using independently characterized system parameters summarized in Table I, we construct error models to realistically capture the behavior of our system. Below, we highlight a few notable aspects of the simulation treatments. 

Any idling time _t_ for metastable state qubits introduces a qubit leakage rate of _pL_ = 1 _−_ exp ( _−t/τ_ ). Under this leakage rate, the erasure fraction is measured to be approximately _re,l ≈_ 0 _._ 72. The Ramsey fringe contrast indicates a physical _T_ 2<sup>_∗_= 0</sup><sup>_._39s,exhibitingaprofileofGaussiandecay.Therefore,afterthequbitsspend</sup><sup>_t_prep= 30msonthe</sup> equator of the Bloch sphere in the encoding circuit, we insert a _Z_ error with a probability of 1 _−_ exp [ _−_ ( _t_ prep _/T_ 2<sup>_∗_)2] on</sup> each physical qubit. During the waiting time _t_ wait, since a Hahn echo is applied, _T_ 2 becomes the relevant timescale. Hence, we insert a _Z_ error with a probability of 1 _−_ exp ( _−t_ wait _/T_ 2), as it exhibits an exponential-decay profile. 

14 


![](.figures/arxiv__2506.13724/2506.13724.pdf-0014-01.png)


<!-- Start of picture text -->
virtual Z rotation virtual Z rotation virtual Z rotation<br>a<br>1 1<br>2 2<br>Prepare<br>3 = 3<br>4 4<br>b c Flip qubit #1 and #2<br>1 1<br>1<br>2 2<br>2<br>Prepare Prepare<br>3 = 3 Prepare<br>3 logical<br>state<br>4 4<br>4<br>Measure in  X -basis<br>d e Echo Transversal entangling gates<br>= Controlled-Z gate<br>Gate zone<br>Storage zone<br>Transversal entangling gates<br><!-- End of picture text -->

Figure S7. **Experimental implementation of quantum circuits.** (a) Encoding circuit for preparing logical qubit states _|_ 00 _⟩L_ with the [[4 _,_ 2 _,_ 2]] code. A flag qubit is used to herald certain Pauli errors and leakage errors during the preparation circuit. (b) _|_ ++ _⟩L_ can be prepared by adding extra _Ry_ ( _π/_ 2) gates on all data qubits after preparing _|_ 00 _⟩L_ . (c) Circuit for the “encode-hold-decode” experiment. Logical qubits are measured directly in the _Z_ -basis, or in the _X_ -basis by inserting an additional _π/_ 2-pulse. During the wait, we implement a Hahn echo sequence to extend the coherence time. Before the final measurement, we apply an extra _π_ rotation on the first and second physical qubit to prevent the misidentification mentioned in the text. (d) The native entangling gates are a CZ gate up to a single qubit phase rotation _θ ≈−_ 3 _._ 4 rad. Moreover, throughout this figure, we use purple (grey) shade to represent operations applied in the gate (storage) zones. (e) Teleportation circuit on distinct logical blocks encoded by the [[4 _,_ 2 _,_ 2]] code. 

|Metric<br>|Value|
|---|---|
|Optical pumping error (<sup>1</sup>S0 _↔_<sup>3</sup>P0 round trip) _ϵ_OP|0_._60(3)%|
|Spin readout error _ϵ_RO|0_._3(2)%|
|Leakage error during transportation|0_._5(1)%|
|Dephasing error per storage-gate zone trip|0_._2%|
|Single-qubit Cliford gate error _ϵ_1Q|0_._10(1)%|
|Single-qubit Cliford erasure fraction _re,_SQ|_∼_0_._56|
|AR CZ gate error _ϵ_CZ|1_._7%|
|AR CZ erasure fraction _re,_CZ|_∼_0_._31|
|_T _<sup>_∗_</sup><br>2 <sup>(Gaussian)</sup>|0.39(1) s|
|_T_1 (exponential)|13 s|
|_T_2 (exponential)|6(2) s|
|3P0 lifetime _τ_ (exponential)|1.64(3) s|
|Erasure fraction while idling _re,_idle|_∼_0_._72|
|Erasure fraction while moving _re,_move|_∼_0_._5|



Table I. Summary of parameters used in the numerical simulation, extracted from independent benchmarking experiments. Note that the transport dephasing error is specified for the sub-optimal polarization configuration used in the QEC circuits. 

15 

The relaxation time _T_ 1 is much longer than _t_ prep and more relevant to _t_ wait (up to 0.5 s) and also shows an exponential-decay profile, so we apply a bit-flip error with a probability of 1 _−_ exp ( _−t_ wait _/T_ 1) on each physical qubit after the waiting time. 

The error model for single-qubit RF gates is based on the single-qubit depolarizing channel, together with leakage out of the metastable manifolds and the same erasure fraction _re,l_ . The total error rate of a single-qubit gate is measured to be _ϵ_ 1Q = 1 _._ 0 _×_ 10<sup>_−_3</sup> . Since a single-qubit gate takes _t_ 1Q = 1 _._ 13 ms, the probability of leakage during a single-qubit gate is _pL,_ 1Q = 1 _−_ exp ( _−t_ 1Q _/τ_ ) = 7 _×_ 10<sup>_−_4</sup> . The remaining error rate _ϵd,_ 1Q = _ϵ_ 1Q _− pL,_ 1Q = 3 _×_ 10<sup>_−_4</sup> is therefore contributed by the depolarizing channel. 

The total error rate of the two-qubit entangling gate is measured to be _ϵ_ CZ = 0 _._ 016(1), the error model in simulation is a combination of Rydberg decay channel and depolarizing errors. Using the experimentally measured Rydberg decay branching ratios [26], we reconstruct the decay process as consisting of three outcomes: erasure to the ground state (<sup>1</sup> S0, with erasure fraction _re,_ CZ), Pauli-type errors to the metastable state (<sup>3</sup> P0), and leakage to other states. All remaining errors are modeled as a Pauli error. The Pauli error is expected to be predominantly _Z_ -type. This is because the dominant sources of error—such as Doppler shifts, laser phase noise, and control imperfections—do not induce population transfer between _|_ 0 _⟩_ and _|_ 1 _⟩_ . Additionally, while the fidelity of the local phase gate is not directly measured, we model it using a noise channel with an error rate comparable to that of the CZ gate, since it is also mediated by the Rydberg laser. 

The qubit state preparation, measurement, and mid-circuit erasure detection methods are detailed in Ref. I A. Qubit initialization is performed through optical pumping (OP), and spin-state readout utilizes Rydberg transition and auto-ionization (RO), resulting in a combined state preparation and measurement error rate primarily due to atom loss, quantified as _ϵ_ OP + _ϵ_ RO = 0 _._ 009. Terminal qubit imaging is implemented via the<sup>1</sup> S0 to<sup>3</sup> P1 (556 nm) transition, with a false positive rate of _ϵ_ term,FP = 0 _._ 001 and a false negative rate of _ϵ_ term,FN = 0 _._ 005. Mid-circuit erasure detection is accomplished through the<sup>1</sup> S0 to<sup>1</sup> P1 (399 nm) transition, characterized by a false positive rate of _ϵ_ ed,FP = 0 _._ 014 and a false negative rate of _ϵ_ ed,FN = 0 _._ 014. 

- [1] C. Ryan-Anderson, J. Bohnet, K. Lee, D. Gresh, A. Hankin, J. Gaebler, D. Francois, A. Chernoguzov, D. Lucchetti, N. Brown, T. Gatterman, S. Halit, K. Gilmore, J. Gerber, B. Neyenhuis, D. Hayes, and R. Stutz, Physical Review X **11** , 041058 (2021), publisher: American Physical Society. 

- [2] L. Egan, D. M. Debroy, C. Noel, A. Risinger, D. Zhu, D. Biswas, M. Newman, M. Li, K. R. Brown, M. Cetina, and C. Monroe, Nature **598** , 281 (2021). 

- [3] R. S. Gupta, N. Sundaresan, T. Alexander, C. J. Wood, S. T. Merkel, M. B. Healy, M. Hillenbrand, T. Jochym-O’Connor, J. R. Wootton, T. J. Yoder, A. W. Cross, M. Takita, and B. J. Brown, Nature **625** , 259 (2024). 

- [4] D. Bluvstein, S. J. Evered, A. A. Geim, S. H. Li, H. Zhou, T. Manovitz, S. Ebadi, M. Cain, M. Kalinowski, D. Hangleiter, J. P. Bonilla Ataides, N. Maskara, I. Cong, X. Gao, P. Sales Rodriguez, T. Karolyshyn, G. Semeghini, M. J. Gullans, M. Greiner, V. Vuleti´c, and M. D. Lukin, Nature **626** , 58 (2024). 

- [5] A. Paetznick, M. P. d. Silva, C. Ryan-Anderson, J. M. Bello-Rivas, J. P. C. III, A. Chernoguzov, J. M. Dreiling, C. Foltz, F. Frachon, J. P. Gaebler, T. M. Gatterman, L. Grans-Samuelsson, D. Gresh, D. Hayes, N. Hewitt, C. Holliman, C. V. Horst, J. Johansen, D. Lucchetti, Y. Matsuoka, M. Mills, S. A. Moses, B. Neyenhuis, A. Paz, J. Pino, P. Siegfried, A. Sundaram, D. Tom, S. J. Wernli, M. Zanner, R. P. Stutz, and K. M. Svore, Demonstration of logical qubits and repeated error correction with better-than-physical error rates (2024), arXiv:2404.02280 [quant-ph]. 

- [6] B. W. Reichardt, A. Paetznick, D. Aasen, I. Basov, J. M. Bello-Rivas, P. Bonderson, R. Chao, W. v. Dam, M. B. Hastings, A. Paz, M. P. d. Silva, A. Sundaram, K. M. Svore, A. Vaschillo, Z. Wang, M. Zanner, W. B. Cairncross, C.A. Chen, D. Crow, H. Kim, J. M. Kindem, J. King, M. McDonald, M. A. Norcia, A. Ryou, M. Stone, L. Wadleigh, K. Barnes, P. Battaglino, T. C. Bohdanowicz, G. Booth, A. Brown, M. O. Brown, K. Cassella, R. Coxe, J. M. Epstein, M. Feldkamp, C. Griger, E. Halperin, A. Heinz, F. Hummel, M. Jaffe, A. M. W. Jones, E. Kapit, K. Kotru, J. Lauigan, M. Li, J. Marjanovic, E. Megidish, M. Meredith, R. Morshead, J. A. Muniz, S. Narayanaswami, C. Nishiguchi, T. Paule, K. A. Pawlak, K. L. Pudenz, D. R. P´erez, J. Simon, A. Smull, D. Stack, M. Urbanek, R. J. M. v. d. Veerdonk, Z. Vendeiro, R. T. Weverka, T. Wilkason, T.-Y. Wu, X. Xie, E. Zalys-Geller, X. Zhang, and B. J. Bloom, Logical computation demonstrated with a neutral atom quantum processor (2024), arXiv:2411.11822 [quant-ph]. 

- [7] Google Quantum AI and Collaborators, Nature **638** , 920 (2025). 

- [8] S. Bravyi, A. W. Cross, J. M. Gambetta, D. Maslov, P. Rall, and T. J. Yoder, Nature **627** , 778 (2024). 

- [9] H. Zhou, C. Zhao, M. Cain, D. Bluvstein, C. Duckering, H.-Y. Hu, S.-T. Wang, A. Kubica, and M. D. Lukin, Algorithmic Fault Tolerance for Fast Quantum Computing (2024), arXiv:2406.17653 [quant-ph]. 

- [10] C. Gidney, N. Shutty, and C. Jones, Magic state cultivation: growing T states as cheap as CNOT gates (2024), arXiv:2409.17595 [quant-ph]. 

- [11] C. Gidney and A. G. Fowler, Quantum **3** , 135 (2019). 

- [12] B. Bauer, S. Bravyi, M. Motta, and G. K.-L. Chan, Chemical Reviews **120** , 12685 (2020). 

- [13] A. Caesura, C. L. Cortes, W. Pol, S. Sim, M. Steudtner, G.-L. R. Anselmetti, M. Degroote, N. Moll, R. Santagati, M. Streif, 

16 

   - and C. S. Tautermann, Faster quantum chemistry simulations on a quantum computer with improved tensor factorization and active volume compilation (2025), arXiv:2501.06165 [quant-ph]. 

- [14] P. Aliferis and J. Preskill, Phys. Rev. A **78** , 052331 (2008). 

- [15] J. P. Bonilla Ataides, D. K. Tuckett, S. D. Bartlett, S. T. Flammia, and B. J. Brown, Nature Communications **12** , 2172 (2021). 

- [16] S. Puri, L. St-Jean, J. A. Gross, A. Grimm, N. E. Frattini, P. S. Iyer, A. Krishna, S. Touzard, L. Jiang, A. Blais, S. T. Flammia, and S. M. Girvin, Science Advances **6** , eaay5901 (2020). 

- [17] U. R´eglade, A. Bocquet, R. Gautier, J. Cohen, A. Marquet, E. Albertinale, N. Pankratova, M. Hall´en, F. Rautschke, L.-A. Sellem, P. Rouchon, A. Sarlette, M. Mirrahimi, P. Campagne-Ibarcq, R. Lescanne, S. Jezouin, and Z. Leghtas, Nature **629** , 778 (2024). 

- [18] H. Putterman, K. Noh, C. T. Hann, G. S. MacCabe, S. Aghaeimeibodi, R. N. Patel, M. Lee, W. M. Jones, H. Moradinejad, R. Rodriguez, N. Mahuli, J. Rose, J. C. Owens, H. Levine, E. Rosenfeld, P. Reinhold, L. Moncelsi, J. A. Alcid, N. Alidoust, P. Arrangoiz-Arriola, J. Barnett, P. Bienias, H. A. Carson, C. Chen, L. Chen, H. Chinkezian, E. M. Chisholm, M.-H. Chou, A. Clerk, A. Clifford, R. Cosmic, A. V. Curiel, E. Davis, L. DeLorenzo, J. M. D’Ewart, A. Diky, N. D’Souza, P. T. Dumitrescu, S. Eisenmann, E. Elkhouly, G. Evenbly, M. T. Fang, Y. Fang, M. J. Fling, W. Fon, G. Garcia, A. V. Gorshkov, J. A. Grant, M. J. Gray, S. Grimberg, A. L. Grimsmo, A. Haim, J. Hand, Y. He, M. Hernandez, D. Hover, J. S. C. Hung, M. Hunt, J. Iverson, I. Jarrige, J.-C. Jaskula, L. Jiang, M. Kalaee, R. Karabalin, P. J. Karalekas, A. J. Keller, A. Khalajhedayati, A. Kubica, H. Lee, C. Leroux, S. Lieu, V. Ly, K. V. Madrigal, G. Marcaud, G. McCabe, C. Miles, A. Milsted, J. Minguzzi, A. Mishra, B. Mukherjee, M. Naghiloo, E. Oblepias, G. Ortuno, J. Pagdilao, N. Pancotti, A. Panduro, J. Paquette, M. Park, G. A. Peairs, D. Perello, E. C. Peterson, S. Ponte, J. Preskill, J. Qiao, G. Refael, R. Resnick, A. Retzker, O. A. Reyna, M. Runyan, C. A. Ryan, A. Sahmoud, E. Sanchez, R. Sanil, K. Sankar, Y. Sato, T. Scaffidi, S. Siavoshi, P. Sivarajah, T. Skogland, C.-J. Su, L. J. Swenson, S. M. Teo, A. Tomada, G. Torlai, E. A. Wollack, Y. Ye, J. A. Zerrudo, K. Zhang, F. G. S. L. Brand˜ao, M. H. Matheny, and O. Painter, Nature **638** , 927 (2025). 

- [19] M. Grassl, T. Beth, and T. Pellizzari, Physical Review A **56** , 33 (1997). 

- [20] C. H. Bennett, D. P. DiVincenzo, and J. A. Smolin, Physical Review Letters **78** , 3217 (1997). 

- [21] W. C. Campbell, Phys. Rev. A **102** , 022426 (2020). 

- [22] Y. Wu, S. Kolkowitz, S. Puri, and J. D. Thompson, Nature Communications **13** , 4657 (2022). 

- [23] A. Kubica, A. Haim, Y. Vaknin, H. Levine, F. Brand˜ao, and A. Retzker, Phys. Rev. X **13** , 041022 (2023). 

- [24] S. D. Barrett and T. M. Stace, Phys. Rev. Lett. **105** , 200502 (2010). 

- [25] K. Sahay, J. Jin, J. Claes, J. D. Thompson, and S. Puri, Physical Review X **13** , 041013 (2023). 

- [26] S. Ma, G. Liu, P. Peng, B. Zhang, S. Jandura, J. Claes, A. P. Burgers, G. Pupillo, S. Puri, and J. D. Thompson, Nature **622** , 279 (2023). 

- [27] P. Scholl, A. L. Shaw, R. B.-S. Tsai, R. Finkelstein, J. Choi, and M. Endres, Nature **622** , 273 (2023). 

- [28] H. Levine, A. Haim, J. Hung, N. Alidoust, M. Kalaee, L. DeLorenzo, E. Wollack, P. Arrangoiz-Arriola, A. Khalajhedayati, R. Sanil, H. Moradinejad, Y. Vaknin, A. Kubica, D. Hover, S. Aghaeimeibodi, J. Alcid, C. Baek, J. Barnett, K. Bawdekar, P. Bienias, H. Carson, C. Chen, L. Chen, H. Chinkezian, E. Chisholm, A. Clifford, R. Cosmic, N. Crisosto, A. Dalzell, E. Davis, J. D’Ewart, S. Diez, N. D’Souza, P. Dumitrescu, E. Elkhouly, M. Fang, Y. Fang, S. Flammia, M. Fling, G. Garcia, M. Gharzai, A. Gorshkov, M. Gray, S. Grimberg, A. Grimsmo, C. Hann, Y. He, S. Heidel, S. Howell, M. Hunt, J. Iverson, I. Jarrige, L. Jiang, W. Jones, R. Karabalin, P. Karalekas, A. Keller, D. Lasi, M. Lee, V. Ly, G. MacCabe, N. Mahuli, G. Marcaud, M. Matheny, S. McArdle, G. McCabe, G. Merton, C. Miles, A. Milsted, A. Mishra, L. Moncelsi, M. Naghiloo, K. Noh, E. Oblepias, G. Ortuno, J. Owens, J. Pagdilao, A. Panduro, J.-P. Paquette, R. Patel, G. Peairs, D. Perello, E. Peterson, S. Ponte, H. Putterman, G. Refael, P. Reinhold, R. Resnick, O. Reyna, R. Rodriguez, J. Rose, A. Rubin, M. Runyan, C. Ryan, A. Sahmoud, T. Scaffidi, B. Shah, S. Siavoshi, P. Sivarajah, T. Skogland, C.-J. Su, L. Swenson, J. Sylvia, S. Teo, A. Tomada, G. Torlai, M. Wistrom, K. Zhang, I. Zuk, A. Clerk, F. Brand˜ao, A. Retzker, and O. Painter, Physical Review X **14** , 011051 (2024). 

- [29] K. S. Chou, T. Shemma, H. McCarrick, T.-C. Chien, J. D. Teoh, P. Winkel, A. Anderson, J. Chen, J. C. Curtis, S. J. de Graaf, J. W. O. Garmon, B. Gudlewski, W. D. Kalfus, T. Keen, N. Khedkar, C. U. Lei, G. Liu, P. Lu, Y. Lu, A. Maiti, L. Mastalli-Kelly, N. Mehta, S. O. Mundhada, A. Narla, T. Noh, T. Tsunoda, S. H. Xue, J. O. Yuan, L. Frunzio, J. Aumentado, S. Puri, S. M. Girvin, S. H. Moseley, and R. J. Schoelkopf, Nature Physics **20** , 1454 (2024). 

- [30] X. Shi, J. Sinanan-Singh, K. DeBry, S. L. Todaro, I. L. Chuang, and J. Chiaverini, Phys. Rev. A **111** , L020601 (2025). 

- [31] W. Huang, X. Sun, J. Zhang, Z. Guo, P. Huang, Y. Liang, Y. Liu, D. Sun, Z. Wang, Y. Xiong, X. Yang, J. Zhang, L. Zhang, J. Chu, W. Guo, J. Jiang, S. Liu, J. Niu, J. Qiu, Z. Tao, Y. Zhou, X. Linpeng, Y. Zhong, and D. Yu, Logical multi-qubit entanglement with dual-rail superconducting qubits (2025), arXiv:2504.12099 [quant-ph]. 

- [32] S. Jandura, J. D. Thompson, and G. Pupillo, PRX Quantum **4** , 020336 (2023). 

- [33] C. Fromonteil, D. Bluvstein, and H. Pichler, PRX Quantum **4** , 020335 (2023). 

- [34] H. Levine, A. Keesling, G. Semeghini, A. Omran, T. T. Wang, S. Ebadi, H. Bernien, M. Greiner, V. Vuleti´c, H. Pichler, and M. D. Lukin, Phys. Rev. Lett. **123** , 170503 (2019). 

- [35] S. Jandura and G. Pupillo, Quantum **6** , 712 (2022). 

- [36] S. J. Evered, D. Bluvstein, M. Kalinowski, S. Ebadi, T. Manovitz, H. Zhou, S. H. Li, A. A. Geim, T. T. Wang, N. Maskara, H. Levine, G. Semeghini, M. Greiner, V. Vuleti´c, and M. D. Lukin, Nature **622** , 268 (2023). 

- [37] R. B.-S. Tsai, X. Sun, A. L. Shaw, R. Finkelstein, and M. Endres, PRX Quantum **6** , 010331 (2025). 

- [38] L. Stefanazzi, K. Treptow, N. Wilcer, C. Stoughton, S. Montella, C. Bradford, G. Cancelo, S. Saxena, H. Arnaldi, S. Sussman, A. Houck, A. Agrawal, H. Zhang, C. Ding, and D. I. Schuster, Review of Scientific Instruments **93** , 044709 (2022). 

- [39] M. Peper, Y. Li, D. Y. Knapp, M. Bileska, S. Ma, G. Liu, P. Peng, B. Zhang, S. P. Horvath, A. P. Burgers, and J. D. 

17 

Thompson, Phys. Rev. X **15** , 011009 (2025). 

- [40] J. Beugnon, C. Tuchendler, H. Marion, A. Ga¨etan, Y. Miroshnychenko, Y. R. P. Sortais, A. M. Lance, M. P. A. Jones, G. Messin, A. Browaeys, and P. Grangier, Nature Physics **3** , 696 (2007), publisher: Nature Publishing Group. 

- [41] D. Bluvstein, H. Levine, G. Semeghini, T. T. Wang, S. Ebadi, M. Kalinowski, A. Keesling, N. Maskara, H. Pichler, M. Greiner, V. Vuleti´c, and M. D. Lukin, Nature **604** , 451 (2022). 

- [42] H. J. Manetsch, G. Nomura, E. Bataille, K. H. Leung, X. Lv, and M. Endres, A tweezer array with 6100 highly coherent atomic qubits (2024), arXiv:2403.12021 [quant-ph]. 

- [43] S. Ma, A. P. Burgers, G. Liu, J. Wilson, B. Zhang, and J. D. Thompson, Physical Review X **12** , 021028 (2022). 

- [44] A. Jenkins, J. W. Lis, A. Senoo, W. F. McGrew, and A. M. Kaufman, Physical Review X **12** , 021027 (2022). 

- [45] K. Barnes, P. Battaglino, B. J. Bloom, K. Cassella, R. Coxe, N. Crisosto, J. P. King, S. S. Kondov, K. Kotru, S. C. Larsen, J. Lauigan, B. J. Lester, M. McDonald, E. Megidish, S. Narayanaswami, C. Nishiguchi, R. Notermans, L. S. Peng, A. Ryou, T.-Y. Wu, and M. Yarwood, Nature Communications **13** , 2779 (2022). 

- [46] J. W. Lis, A. Senoo, W. F. McGrew, F. R¨onchen, A. Jenkins, and A. M. Kaufman, Physical Review X **13** , 041035 (2023). 

- [47] S. G. Porsev, A. Derevianko, and E. N. Fortson, Physical Review A **69** , 021403 (2004). 

- [48] J. D. Thompson, T. G. Tiecke, A. S. Zibrov, V. Vuleti´c, and M. D. Lukin, Physical Review Letters **110** , 133001 (2013). 

- [49] N. M. Linke, M. Gutierrez, K. A. Landsman, C. Figgatt, S. Debnath, K. R. Brown, and C. Monroe, Science Advances **3** , e1701074 (2017). 

- [50] C. K. Andersen, A. Remm, S. Lazar, S. Krinner, N. Lacroix, G. J. Norris, M. Gabureac, C. Eichler, and A. Wallraff, Nature Physics **16** , 875 (2020). 

- [51] E. Knill, Nature **434** , 39 (2005). 

- [52] S. Bartolucci, P. Birchall, H. Bomb´ın, H. Cable, C. Dawson, M. Gimeno-Segovia, E. Johnston, K. Kieling, N. Nickerson, M. Pant, F. Pastawski, T. Rudolph, and C. Sparrow, Nature Communications **14** , 912 (2023). 

- [53] S. Paesani and B. J. Brown, Physical Review Letters **131** , 120603 (2023). 

- [54] A. P. Burgers, S. Ma, S. Saskin, J. Wilson, M. A. Alarc´on, C. H. Greene, and J. D. Thompson, PRX Quantum **3** , 020326 (2022). 

- [55] B. Zhang, P. Peng, A. Paul, and J. D. Thompson, Optica **11** , 227 (2024). 

- [56] P. Aliferis and B. M. Terhal, Quantum Info. Comput. **7** , 139 (2007). 

- [57] M. Norcia, W. Cairncross, K. Barnes, P. Battaglino, A. Brown, M. Brown, K. Cassella, C.-A. Chen, R. Coxe, D. Crow, J. Epstein, C. Griger, A. Jones, H. Kim, J. Kindem, J. King, S. Kondov, K. Kotru, J. Lauigan, M. Li, M. Lu, E. Megidish, J. Marjanovic, M. McDonald, T. Mittiga, J. Muniz, S. Narayanaswami, C. Nishiguchi, R. Notermans, T. Paule, K. Pawlak, L. Peng, A. Ryou, A. Smull, D. Stack, M. Stone, A. Sucich, M. Urbanek, R. van de Veerdonk, Z. Vendeiro, T. Wilkason, T.-Y. Wu, X. Xie, X. Zhang, and B. Bloom, Physical Review X **13** , 041034 (2023). 

- [58] M. N. H. Chow, V. Buchemmavari, S. Omanakuttan, B. J. Little, S. Pandey, I. H. Deutsch, and Y.-Y. Jau, PRX Quantum **5** , 040343 (2024). 

- [59] Y. Li, Y. Bao, M. Peper, C. Li, and J. D. Thompson (2025), in preparation. 

- [60] S. Gu, Y. Vaknin, A. Retzker, and A. Kubica, Optimizing quantum error correction protocols with erasure qubits (2024), arXiv:2408.00829 [quant-ph]. 

- [61] K. Chang, S. Singh, J. Claes, K. Sahay, J. Teoh, and S. Puri, Surface Code with Imperfect Erasure Checks (2024), arXiv:2408.00842 [quant-ph]. 

- [62] H. Perrin, S. Jandura, and G. Pupillo, Quantum Error Correction resilient against Atom Loss (2025), arXiv:2412.07841 [quant-ph]. 

- [63] C.-C. Yu, Z.-H. Chen, Y.-H. Deng, M.-C. Chen, C.-Y. Lu, and J.-W. Pan, Processing and Decoding Rydberg Decay Error with MBQC (2025), arXiv:2411.04664 [quant-ph]. 

- [64] G. Baranes, M. Cain, J. P. B. Ataides, D. Bluvstein, J. Sinclair, V. Vuletic, H. Zhou, and M. D. Lukin, Leveraging Atom Loss Errors in Fault Tolerant Quantum Algorithms (2025), arXiv:2502.20558 [quant-ph]. 

- [65] K. Singh, S. Anand, A. Pocklington, J. T. Kemp, and H. Bernien, Phys. Rev. X **12** , 011040 (2022). 

- [66] J. A. Muniz, D. Crow, H. Kim, J. M. Kindem, W. B. Cairncross, A. Ryou, T. C. Bohdanowicz, C.-A. Chen, Y. Ji, A. M. W. Jones, E. Megidish, C. Nishiguchi, M. Urbanek, L. Wadleigh, T. Wilkason, D. Aasen, K. Barnes, J. M. BelloRivas, I. Bloomfield, G. Booth, A. Brown, M. O. Brown, K. Cassella, G. Cowan, J. Epstein, M. Feldkamp, C. Griger, Y. Hassan, A. Heinz, E. Halperin, T. Hofler, F. Hummel, M. Jaffe, E. Kapit, K. Kotru, J. Lauigan, J. Marjanovic, M. Meredith, M. McDonald, R. Morshead, S. Narayanaswami, K. A. Pawlak, K. L. Pudenz, D. R. P´erez, P. Sabharwal, J. Simon, A. Smull, M. Sorensen, D. T. Stack, M. Stone, L. Taneja, R. J. M. v. d. Veerdonk, Z. Vendeiro, R. T. Weverka, K. White, T.-Y. Wu, X. Xie, E. Zalys-Geller, X. Zhang, J. King, B. J. Bloom, and M. A. Norcia, Repeated ancilla reuse for logical computation on a neutral atom quantum computer (2025), arXiv:2506.09936 [quant-ph]. 

- [67] A. Senoo, A. Baumg¨artner, J. W. Lis, G. M. Vaidya, Z. Zeng, G. Giudici, H. Pichler, and A. M. Kaufman (2025), in preparation. 

- [68] D. A. Rower, L. Ding, H. Zhang, M. Hays, J. An, P. M. Harrington, I. T. Rosen, J. M. Gertler, T. M. Hazard, B. M. Niedzielski, M. E. Schwartz, S. Gustavsson, K. Serniak, J. A. Grover, and W. D. Oliver, PRX Quantum **5** , 040342 (2024). 

- [69] T. Flash and N. Hogan, Journal of Neuroscience **5** , 1688 (1985). 

- [70] A. W. Young, W. J. Eckner, W. R. Milner, D. Kedar, M. A. Norcia, E. Oelker, N. Schine, J. Ye, and A. M. Kaufman, Nature **588** , 408 (2020). 

- [71] L. D. Dickson, Applied Optics **11** , 2196 (1972). 

- [72] S. Kuhr, W. Alt, D. Schrader, I. Dotsenko, Y. Miroshnychenko, A. Rauschenbeutel, and D. Meschede, Physical Review A **72** , 023406 (2005). 

18 

- [73] K. P. Beloy and A. D. Ludlow, private communication (2025). 

- [74] G. Bornet, G. Emperauger, C. Chen, B. Ye, M. Block, M. Bintz, J. A. Boyd, D. Barredo, T. Comparin, F. Mezzacapo, T. Roscilde, T. Lahaye, N. Y. Yao, and A. Browaeys, Nature **621** , 728 (2023). 

- [75] T. G. Tiecke, J. D. Thompson, N. P. de Leon, L. R. Liu, V. Vuleti´c, and M. D. Lukin, Nature **508** , 241 (2014).

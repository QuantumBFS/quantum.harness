---
source: "https://arxiv.org/abs/2606.05060"
type: "arxiv"
canonical_id: "2606.05060"
title: "High-fidelity neutral atom gates leveraging low-rank Hessian optimization"
authors: "Liu, Genyue, Bornet, Guillaume, Kurdak, Deniz, Xiao, Mingxuan, Li, Chenyuan, Zhang, Bichen, Thompson, Jeff D."
year: "2026"
arxiv_id: "2606.05060"
full_text: yes
---

# High-fidelity neutral atom gates leveraging low-rank Hessian optimization

**Authors:** Liu, Genyue, Bornet, Guillaume, Kurdak, Deniz, Xiao, Mingxuan, Li, Chenyuan, Zhang, Bichen, Thompson, Jeff D.

**Citation:** preprint, 2026

**arXiv:** [2606.05060](https://arxiv.org/abs/2606.05060)

## Abstract

Quantum optimal control can produce fast and robust multi-qubit gates, but experimentally calibrating the resulting high-dimensional waveforms remains challenging because direct searches over large parameter spaces converge slowly. Building on the low-rank structure of quantum-control landscapes, we develop and benchmark a Hessian-based calibration method for optimal-control gates. The method identifies the few waveform directions that affect fidelity to leading order, with the number of directions set by the accessible leakage and coherent error channels, and optimizes only within this principal space using closed-loop experimental feedback. We apply this approach to an amplitude-robust controlled-Z gate on metastable-state 171Yb nuclear-spin qubits. Experimentally, we verify the predicted Hessian-sensitive directions and demonstrate rapid convergence of the optimization protocol. The optimized gate reaches a raw fidelity of 0.9959(2), increasing to 0.99902(7) after postselection on no detected loss, and the performance is essentially unchanged under laser-power variations of up to 20%. We further show that the same fidelity Hessian directions can correct certain Hamiltonian parameter errors. These results establish low-rank Hessian optimization as an efficient and physically motivated calibration strategy for high-dimensional optimal-control gates, which is broadly applicable to many qubit types.

## Full Text

# **High-fidelity neutral atom gates leveraging low-rank Hessian optimization** 

Genyue Liu,<sup>1,</sup><sup>_∗_</sup> Guillaume Bornet,<sup>1,</sup><sup>_∗_</sup> Deniz Kurdak,<sup>1</sup> Mingxuan Xiao,<sup>1</sup> Chenyuan Li,<sup>2</sup> Bichen Zhang,<sup>1</sup> and Jeff D. Thompson<sup>1,</sup><sup>_†_</sup> 

> 1 _Princeton University, Department of Electrical and Computer Engineering, Princeton, New Jersey 08544_ 

> 2 _Princeton University, Department of Physics, Princeton, New Jersey 08544_ 

Quantum optimal control can produce fast and robust multi-qubit gates, but experimentally calibrating the resulting high-dimensional waveforms remains challenging because direct searches over large parameter spaces converge slowly. Building on the low-rank structure of quantum-control landscapes, we develop and benchmark a Hessian-based calibration method for optimal-control gates. The method identifies the few waveform directions that affect fidelity to leading order, with the number of directions set by the accessible leakage and coherent error channels, and optimizes only within this principal space using closed-loop experimental feedback. We apply this approach to an amplitude-robust controlled- _Z_ gate on metastable-state<sup>171</sup> Yb nuclear-spin qubits. Experimentally, we verify the predicted Hessian-sensitive directions and demonstrate rapid convergence of the optimization protocol. The optimized gate reaches a raw fidelity of 0.9959(2), increasing to 0.99902(7) after postselection on no detected loss, and the performance is essentially unchanged under laserpower variations of up to 20%. We further show that the same fidelity Hessian directions can correct certain Hamiltonian parameter errors. These results establish low-rank Hessian optimization as an efficient and physically motivated calibration strategy for high-dimensional optimal-control gates, which is broadly applicable to many qubit types. 

High-fidelity gates are a central requirement for quantum computing and especially for fault-tolerant architectures, where physical gate errors strongly affect the overhead needed for error correction. Quantum optimal control is an important tool for pushing gate performance beyond simple analytic pulses [1–5]. By shaping timedependent control fields, optimal control can produce gates that are faster, more robust, and better adapted to realistic experimental constraints [2, 6–14]. 

However, realizing this benefit in practice is challenging: the pulses are only as accurate as the model Hamiltonian used to optimize them, and can only be implemented as faithfully as the transfer function of the devices generating the physical control fields. The power of optimal control comes from using an expressive, high-dimensional basis set of control waveforms, but experimentally optimizing a high-dimensional space is prohibitive. A number of optimization approaches have been explored, including analytically designed pulses [10], parameterized ansatzes [15–17], expansion in a truncated basis set [18–20], machine learning [21, 22], and genetic algorithms [23]. However, these approaches have shortcomings, including requiring many experimental samples, not converging to the optimal fidelity, or depending sensitively on independent characterizations of the Hamiltonian or transfer function. 

Pioneering theoretical work in quantum optimal control has established that the fidelity landscape around any optimum is robust, in the sense that the fidelity is insensitive to most perturbations of the gate itself [24– 26]. This insight was recently used to identify a reduceddimensional parameter space for experimental optimization of single-qubit gates in a superconducting proces- 

> _∗_ These authors contributed equally to this work. 

> _†_ jdthompson@princeton.edu 

sor [27]. However, the application of these techniques to optimizing multi-qubit gates, model Hamiltonian errors, and leakage errors is an open challenge. 

In this work, we theoretically develop and experimentally benchmark a rigorous model of the sensitivity of multi-qubit gates to control and Hamiltonian errors. We provide an explicit formula for the rank of the space of control waveform perturbations that affect the gate fidelity, expressed in terms of the number of error channels in the target unitary, including leakage to non-computational states. We argue that experimental optimization of the waveform within this restricted space is both necessary and sufficient to correct small but arbitrary errors in the control waveform and many errors in the model Hamiltonian. In the context of twoqubit entangling gates on neutral atom qubits, the relevant control space rank is only 5 or 10 depending on the number of Rydberg levels involved. We apply this to optimize the fidelity of an amplitude-robust controlled-Z (CZ) gate in metastable<sup>171</sup> Yb qubits, reaching an ultimate fidelity of _F_ = 0 _._ 9959(2) [ _F_ ps = 0 _._ 99902(7) postselected on survival]. These results establish low-rank Hessian optimization as an efficient and physically motivated method for calibrating optimal-control gates, with potential applications beyond neutral-atom processors. 

### **I. LOW-RANK HESSIAN OPTIMIZATION** 

We develop the concept of low-rank Hessian optimization in the context of entangling gates for neutral atom qubits based on the Rydberg blockade [28–30]. The most common implementation is the symmetric CZ gate, where a single laser field applied to a pair of atoms couples one of the qubit levels in each atom to a Rydberg state [10, 31]. If the atoms are sufficiently close, the van der Waals interaction prevents simultaneously exciting 

2 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0002-01.png)


<!-- Start of picture text -->
c Gate Profile d e f Principal -  vi Null -  v  ⟂<br>a<br>AA Gate Null<br>Space<br>v  ⟂<br>b λ  = 0<br>0 t T v 1 v 2 v 3 v 4 v 5 0 t T 0 t T<br>Distortion mode<br>Optimization<br>g Trajectory h i −1<br>This Work 10<br>−3 Chebyshev (First 6 Orders)<br>10 Analytical Ansatz (AA)<br>AA + Orthogonal Eigenbasis −2<br>Optimized 10−4 10 t t<br>Gate<br>−5 −3<br>10 10<br>−6<br>10 −4<br>10<br>0 10 20 30 40 50 0 10 20 30 40<br>Optimization step Optimization step<br>Increasing Fidelity<br>⃗Ω]<br>|⃗Ω| [ δ<br>Re<br>λi<br>⃗Ω]<br>[ δ<br>Arg(⃗Ω) Im<br>|⃗Ω|<br>Simulated gate error Simulated gate error Arg(⃗Ω)<br><!-- End of picture text -->

FIG. 1. **Symmetric CZ gates and low-rank Hessian optimization.** (a) Minimal three-level system for a symmetric Rydberg-mediated CZ gate, in which a pulse couples the qubit state _|_ 1 _⟩_ to a Rydberg state _|r⟩_ with complex Rabi frequency Ω _≡_ Ω( _t_ ) _e_<sup>_iϕ_(</sup><sup>_t_)</sup> . (b) In the two-qubit basis, the _|_ 01 _⟩_ and _|_ 10 _⟩_ states couple to the Rydberg manifold with Rabi frequency Ω, while the _|_ 11 _⟩_ state couples to the symmetric state _|W ⟩_ = ( _|_ 1 _r⟩_ + _|r_ 1 _⟩_ ) _/_ _~~√~~_ 2 with enhanced strength _~~√~~_ 2 Ω. (c) Amplitude and phase profiles of the analytical ansatz (AA) gate, used here as a representative example for studying pulse-distortion sensitivity. (d) The corresponding Bloch sphere trajectories of the initial states _|_ 11 _⟩_ and _|_ 01 _⟩_ . (e) Eigenvalue spectrum of the fidelity Hessian of the AA pulse. Note that only five eigenvalues are nonzero. (f) Eigenvectors _⃗vi_ of the principal space plotted in their real and imaginary components, together with several null-space modes, _⃗v⊥_ . (g) The optimization procedure corrects the projection of the gate error onto the principal space, _δ⃗_ Ω _∥_ , while ignoring the projection onto the fidelity Hessian null space. (h) Simulated comparison of optimization strategies (see text). Each optimization cycle (solid markers) consists of multiple optimization steps (lighter markers), with the number of steps depending on the chosen optimization strategy. (i) Optimization of distorted initial pulses with three different distortion amplitudes with the AA parametrization. Insets show the corresponding changes to the amplitude and phase of Ω. 

both atoms to the Rydberg state, resulting in the constrained dynamics shown in Fig. 1a and b. This can give rise to a controlled-Z gate through the appropriate choice of drive waveform Ω= Ω( _t_ ) _e_<sup>_iϕ_(</sup><sup>_t_)</sup> . Numerous analytic [10, 12, 16, 31, 32] and numerical [11, 13] variants of this gate have been proposed. 

In practice, both analytic and numerical gates are sensitive to imperfections in the control waveform, or errors in the model used to derive the gate, necessitating closedloop experimental calibration. However, identifying intuitive calibration parameters is challenging. Here, we demonstrate that the eigenvectors of the fidelity Hessian provide a natural, low-rank basis set for closed-loop experimental optimization of arbitrary gates. To analyze the eigenvalue structure, we decompose the gate waveform in an arbitrary orthonormal set of real-valued basis functions _{fk_ ( _t_ ) _}_ with dimension _N ≫_ 1, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0002-05.png)


The real coefficients _αi_ define a control vector Ω= 

_{α_ 1 _, . . . , α_ 2 _N }_ . We denote the intended gate by a control vector Ω0, which implements the target unitary optimally with fidelity _F_ = 1. Given an erroneous gate Ω0 + _δ⃗_ Ω( _i.e._ , from distortion in the control waveform or errors in the model Hamiltonian used to compute Ω0), the gate infidelity can be expressed as: 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0002-08.png)


Here _Hij_ = _− ∂α∂i_<sup>2</sup> _∂αF j_<sup>istheHessianofthegateerror</sup> with respect to the real control parameter _αi_ , evaluated at the designed waveform. Because _H_ is a real symmetric matrix, diagonalizing it gives orthonormal eigenvectors _vi_ with corresponding eigenvalues _λi_ . The eigenvectors identify the waveform distortions to which the gate is sensitive, while the eigenvalues quantify the corresponding sensitivities. Thus, the error reads: 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0002-10.png)


Evaluating this function for a representative Rydberg CZ gate [16, 17] (Fig. 1c and d), we find that 

3 

there are only five nonzero eigenvalues, even though the control waveform dimension _N_ is very large (Fig. 1e). The associated eigenvectors (Fig. 1f) form a subspace _V_ = span _{⃗v_ 1 _, . . . ,⃗vr}_ , which we call the principal space. Any waveform distortion can be decomposed into a component inside _V_ and a component perpendicular to it (Fig. 1g): 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0003-02.png)


The perpendicular component lies in the null space of the Hessian and therefore does not contribute errors to leading order. 

The principal space _V_ is independent of the choice of basis functions _{fk}_ ; it is instead a property of the gate itself, and can be understood from considering the space of accessible errors in the target unitary. In the perturbative regime, a waveform distortion _δ⃗_ Ωinduces only a small change _δU_ in the final unitary relative to the ideal gate _U_ 0. The map from _δ⃗_ Ωto _δU_ can then be approximated by a linear transformation, where _δU_ can be viewed as a tangent vector to _SU_ ( _D_ ), where _D_ is the dimension of the Hilbert space for the gate. Since this tangent space has dimension _D_<sup>2</sup> _−_ 1, the dimensionality of the principal space is also bounded to dim _V ≤ D_<sup>2</sup> _−_ 1 [26, 27]. 

In practice, the relevant rank can be much smaller, because symmetries in the control Hamiltonian restrict the set of possible perturbations _δU_ . The maximum possible Hessian rank for a gate on the Hilbert space _{|_ 0 _⟩ , |_ 1 _⟩ , |r⟩}_<sup>_⊗_2</sup> is 80; however, the smaller rank of five can be explained by a simple formula counting the number of accessible leakage channels and phase errors (Appendix C). Specifically, the two independent leakage channels _|_ 01 _⟩→|_ 0 _r⟩_ and _|_ 11 _⟩→|W ⟩_ each contribute two dimensions (corresponding to the real and imaginary parts of the matrix element), while the nonlinear phase contributes another dimension. In this model, _|_ 10 _⟩_ is related to _|_ 01 _⟩_ by symmetry and does not contribute additional error channels, while _|_ 00 _⟩_ does not experience any dynamics. This explains the observed rank of five. 

This greatly simplifies the experimental optimization: only the component _δ⃗_ Ω _∥_ needs to be corrected, and the basis vectors of _V_ define a set of orthogonal optimization directions (Fig. 1g). In Fig. 1h, we perform simulations comparing this approach with three other optimization schemes used in the literature, and consider two aspects: convergence rate and error floor. Our approach of iteratively optimizing Hessian eigenvectors gives rapid convergence with no fidelity floor. Directly optimizing the polynomial coefficients _αk_ in a chosen basis [19] can also reach the optimum, provided that the basis set is sufficiently large. However, this approach converges much more slowly because the scanned coefficients are generally coupled to one another. In contrast, optimizing the parameters of an analytic ansatz can lead to very slow convergence and an effective error floor if the parameters do not have a large projection onto all axes of the principal space, which is the case for the ansatz in Refs. [16, 17]. Optimizing the principal components 

## **a** 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0003-08.png)


<!-- Start of picture text -->
Prepare Prepare<br>200<br>P 0(1) =  0.17(1)% P 1(1) =  97.53(5)%<br>100<br>P 0(loss) =  1.07(3)% P 1(loss) =  1.65(4)%<br>0 P 0(0) =  98.75(3)% P 1(0) =  0.83(3)%<br>0 100 0 100<br>Counts (1 st  Img) Counts (1 st  Img)<br>b<br>1.00<br>0.95 F ps =  0.999979(9)<br>F  =  0.99935(3)<br>0.90<br>0.85 3P 0<br>0.80<br>0 50 100 150 200 250 300<br>Circuit depth,  d<br> Img)<br>nd<br>Counts (2<br>Success rate<br><!-- End of picture text -->

FIG. 2. **Gate benchmarking with three-outcome measurement.** (a) Photon-count distributions collected from two successive images used to measure the atoms in _|_ 0 _⟩_ and _|_ 1 _⟩_ , respectively. Dashed lines indicate the imageclassification thresholds, and colors indicate the assigned outcomes _|_ 0 _⟩_ , _|_ 1 _⟩_ , and loss. (b) Randomized benchmarking of RF single-qubit gates. The raw fidelity is _F_ = 0 _._ 99935(3) (green), which increases to _F_ ps = 0 _._ 999979(9) (blue) after postselecting on no detected atom loss. In all panels, error bars indicate 1 _σ_ uncertainties. 

within this parameterization can improve the convergence [17], but the effective error floor remains. The magnitude of the error floor depends on the magnitude of the initial waveform error that is orthogonal to the control vectors generated by the analytic pulse parameters (Fig. 1i). 

Connecting the dimension of the principal space to physical error channels also clarifies which Hamiltonian errors can be corrected by the same scan. If a small Hamiltonian perturbation only changes the amplitudes of the leakage, mixing, or phase-error channels already represented in the Hessian eigenvectors, then its leadingorder effect lies within the same low-dimensional correctable space and can be removed by scanning along those directions (Appendix D). 

### **II. EXPERIMENTAL IMPLEMENTATION** 

We now turn to the experimental implementation of our optimization approach. We briefly summarize the experimental context. We study qubits encoded in the nuclear spin sublevels of the<sup>3</sup> _P_ 0 metastable-state manifold of<sup>171</sup> Yb, with _|_ 0 _⟩≡_ ��3 _P_ 0 _, mF_ = _−_ 1 _/_ 2� and _|_ 1 _⟩≡_ ��3 _P_ 0 _, mF_ = 1 _/_ 2� [19, 34]. One advantage of this 

4 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0004-01.png)


<!-- Start of picture text -->
a b c<br>1.0<br>0.5<br>0.0<br>1.0<br>0.5<br>0.0<br>0.0 0.1 0.2 0.3 0.4 0.5<br>Time [µs]<br>d e<br>2|0<br>|Ω/Ω<br>) π<br>/(2<br>ϕ<br><!-- End of picture text -->

FIG. 3. **Verification of the low-rank nature of the fidelity Hessian.** (a) Four-level model of the states involved in the Rydberg gate. (b) Numerically optimized gate waveforms for the amplitude-robust gate. (c) Rydberg population during the gate when starting from _|_ 00 _⟩_ , _|_ 01 _⟩_ , and _|_ 11 _⟩_ . The small Zeeman splitting between _|r⟩_ and _|r_<sup>_′_</sup> _⟩_ results in a significant Rydberg population when starting in _|_ 00 _⟩_ . (d) Comparison between measured (circles) and calculated (squares) sensitivities _λi_ of the CZ gate fidelity to distortions along the Hessian eigenvectors. Inset: representative measurements used to extract the sensitivity, with colors matching the highlighted points in the main figure. The fidelity is extracted using a randomized benchmarking sequence following Ref. [33]. Error bars indicate 1 _σ_ uncertainties. (e) Decomposition of the measured and calculated sensitivities into contributions from leakage errors from different computational states _λ_<sup>_α_</sup> _i_<sup>00</sup> , _λ_<sup>_α_</sup> _i_<sup>01</sup> , and _λ_<sup>_α_</sup> _i_<sup>11</sup> , and coherent error _λ_<sup>_θ_</sup> _i_<sup>.Solid bars denote experimental values (see Appendix C for measurement details), while hatched bars denote</sup> the corresponding theoretical predictions. 

encoding is that gate errors are biased towards transitions outside of the computational subspace, which can be beneficial for error correction whether detected directly [35–37] or later in the form of qubit loss [38–41]. Here, we characterize gates using a three-outcome measurement that distinguishes _|_ 0 _⟩_ , _|_ 1 _⟩_ , and loss [34, 41– 44]. Using a measurement scheme similar to Ref. [42], we acquire two successive images (respectively named 1<sup>st</sup> and 2<sup>nd</sup> in Fig. 2a) to separately determine the _|_ 0 _⟩_ and _|_ 1 _⟩_ population. We observe the correct state with probability 98 _._ 14(3)%, which rises to 99 _._ 49(2)% after discarding loss events. As a demonstration, we apply this measurement to single-qubit randomized benchmarking. The extracted single-qubit gate error is 6 _._ 5(3) _×_ 10<sup>_−_4</sup> , while the error postselected on the absence of loss is reduced to 2 _._ 1(9) _×_ 10<sup>_−_5</sup> . This indicates that over 95% of the single-qubit gate error comes from leakage. 

For the two-qubit gate, we use an amplitude-robust (AR) controlled- _Z_ gate designed by optimal control. The AR design is robust to spatial intensity inhomogeneity and slow temporal drifts of the laser power [12, 13, 37], making it attractive for achieving uniform gate fidelities 

over large gate zones with constrained laser power. In addition to enabling this robustness, optimal control also allows us to design a gate that tolerates other nearby Rydberg states. 

This gate is implemented through the 6 _sνs_ , _ν_ = 52 _._ 3, _F_ = 1 _/_ 2 Rydberg manifold [33]. In our apparatus, the Rydberg-beam polarization and achievable Zeeman splitting are constrained by optical access and available magnetic-field strength. The Rydberg beam is linearly polarized perpendicular to the magnetic field, and therefore decomposes into equal _σ_<sup>_−_</sup> and _σ_<sup>+</sup> components: the _σ_<sup>_−_</sup> component resonantly drives _|_ 1 _⟩→|r⟩≡|ν_ = 52 _._ 3 _, mF_ = _−_ 1 _/_ 2 _⟩_ , while the equally strong _σ_<sup>+</sup> component also couples _|_ 0 _⟩→|r_<sup>_′_</sup> _⟩≡ |ν_ = 52 _._ 3 _, mF_ = +1 _/_ 2 _⟩_ (Fig. 3a). The experimentally available magnetic-field strength in our apparatus limits the Zeeman splitting between these two Rydberg states to ∆ _r_ = 2 _π ×_ 16 _._ 1 MHz, only a few times larger than the gate Rabi frequency Ω0 = 2 _π ×_ 6 _._ 0 MHz (which corresponds to approximately 60 mW of 302 nm laser power for a beam waist on the atoms of _w_ 0 = 12 _µ_ m defined at 1 _/e_<sup>2</sup> ), such that the dynamics of the _|_ 00 _⟩_ state can no 

5 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0005-01.png)


<!-- Start of picture text -->
a b c<br>1.0<br>0.008 1.0<br>Ideal<br>0.5<br>Before 0.9<br>After<br>0.0 0.006 0.8<br>1.0<br>0.7<br>0.5 0.004<br>0.6<br>0.0 0 1 2 3 0 20 40<br>0.0 0.2 0.4 Optimization cycle Circuit depth,  d<br>Time [µs]<br>d e f<br>Raw PS on loss 1.000 Total<br>AR<br>TO 0.999 Rydberg lifetime<br>−2 0.998 Doppler<br>10<br>Imperfect blockade<br>0.997<br>Varying blockade Raw<br>0.996 Laser PN Postselected<br>10 −3 0.995 Laser AN Experiment<br>0.7 0.8 0.9 1.0 1.1 0 5 10 10−5 10−4 10−3<br>Laser intensity,  I / I 0 Time [h] Gate error<br>2|0<br>|Ω/Ω<br>|00⟩<br>P<br>) π CZ gate error<br>/(2<br>ϕ<br>CZ gate error CZ gate fidelity<br><!-- End of picture text -->

FIG. 4. **Optimization and benchmarking of amplitude-robust CZ gates.** (a) Ideal gate waveform, and measured gate waveforms before and after optimization. The measured waveforms are both significantly distorted by the acousto-optic modulator. (b) CZ gate error after several optimization cycles, each consisting of one scan of all 10 Hessian eigenvector coefficients. The dashed line represents the simulated gate error. (c) Echoed RB characterization of the AR CZ gate. The gate error is _ε_ = 4 _._ 0(5) _×_ 10<sup>_−_3</sup> (green) before loss postselection, which is reduced to _ε_ ps = 1 _._ 0(2) _×_ 10<sup>_−_3</sup> (blue) after loss postselection. (d) Sensitivity of the AR CZ gate and non-robust time-optimal (TO) CZ gate to changes in the laser intensity, _I/I_ 0. The curves show phenomenological fits with quadratic scaling in ∆ _I/I_ 0 for the TO gate and quartic scaling for the AR gate, where ∆ _I ≡ I − I_ 0. (e) Long-term stability of the optimized AR CZ gate. (f) Simulated error budget for the AR CZ gate. “Laser PN” denotes laser phase noise, “Laser AN” denotes laser intensity noise. In all panels, error bars indicate 1 _σ_ uncertainties. 

longer be neglected. The resulting gate design and state populations during the gate are shown in Fig. 3b and c. 

The more complicated level structure introduces additional leakage error channels, and the Hessian rank increases to 10 (Appendix C). To validate the low-rank nature of the fidelity Hessian, we measure the gate sensitivity along the 10 principal directions and four randomly chosen directions in the null space. The experimental sensitivities track the predicted sensitivities, with a clear distinction between the measured sensitivity of the lowest principal eigenvector and those of the null eigenvectors (Fig. 3d). In separate benchmarking experiments, we can measure the type of error caused by perturbing each eigenmode, finding good agreement with the theory prediction (Fig. 3e). We note that most eigenmodes are dominated by leakage, suggesting that future calibration routines may be simplified by monitoring selected error channels for these modes. 

Next, we optimize the performance of the two-qubit gate by iteratively scanning the coefficient along each of the 10 principal Hessian eigenvectors. We benchmark the gate fidelity using an echoed global randomized benchmarking sequence [16], which cancels sensitivity to single-qubit phase errors and preserves the number of single-qubit operations. Before optimization, the waveform is significantly distorted by the finite bandwidth 

of the acousto-optic modulator (Fig. 4a), and the gate error rate is _ε_ = 7 _._ 0(4) _×_ 10<sup>_−_3</sup> , roughly double the predicted value. The optimization protocol converges to the expected gate error of _ε_ raw = 4 _._ 0(5) _×_ 10<sup>_−_3</sup> after a single iteration (Fig. 4b). Postselecting on the absence of loss reduces the error to _ε_ ps = 1 _._ 0(2) _×_ 10<sup>_−_3</sup> (Fig. 4c), corresponding to an erasure fraction of 0 _._ 75(6). Importantly, the optimized waveform is only slightly modified from the initial waveform, demonstrating that our optimization approach isolates the low-dimensional waveform space relevant for the gate fidelity. 

A key advantage of the AR gate is that its performance does not rely on precise control of the laser intensity, and we directly test this robustness by deliberately varying the laser power. For comparison, we also study the non-robust time-optimal gate, optimized using the same technique, which achieves a nominal gate error of _ε_ raw = 2 _._ 7(5) _×_ 10<sup>_−_3</sup> before loss postselection, and gate error of _ε_ ps = 1 _._ 0(3) _×_ 10<sup>_−_3</sup> after loss postselection [11]. The time-optimal gate rapidly degrades away from its calibrated intensity, while the AR gate fidelity is essentially unchanged for laser power variations up to 20% (Fig. 4d). Benefiting from this robustness, the AR gate performance remains stable over a 10-hour period without waveform reoptimization, achieving an average error of _<u>ε</u>_ raw = 4 _._ 1(2) _×_ 10<sup>_−_3</sup> before loss postselection, 

6 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0006-01.png)


<!-- Start of picture text -->
a b<br>1.0<br>0.995<br>0.5<br>0.990 0.0<br>1.0<br>Unoptimized<br>0.985 1 opt cycle 0.5<br>2 opt cycle<br>Reference<br>0.0<br>0.0 0.1 0.0 0.2 0.4<br>(Δ r  −Δ 0 r )/Δ r Time [µs]<br>2|0<br>|Ω/Ω<br>) π<br>CZ gate fidelity<br>/(2<br>ϕ<br><!-- End of picture text -->

FIG. 5. **Optimizing gates with Hamiltonian parameter errors.** (a) CZ gate fidelity versus reduction of the Rydberg Zeeman splitting before and after Hessian optimization. A single optimization cycle along the original Hessian eigenvectors eliminates most of the added error, with an additional cycle needed at the largest miscalibration. (b) Optimized laser intensity and phase profiles for the nominal case (red) and the reduced-field case (blue, 1 _−_ ∆<sup>_′_</sup> _r_<sup>_/_∆</sup> _r_<sup>=0</sup><sup>_._14).</sup> Error bars indicate 1 _σ_ uncertainties. 

and _<u>ε</u>_ ps = 9 _._ 8(7) _×_ 10<sup>_−_4</sup> after loss postselection (Fig. 4e). The optimized gate performance is consistent with a detailed numerical model based on independently measured parameters, indicating that the dominant sources of error are Rydberg decay and Doppler shifts (Fig. 4f). We attribute the small discrepancy in the postselected error probability to the difficulty of quantitatively modeling the full Rydberg interaction, including unwanted excitation to _|r_<sup>_′_</sup> _⟩_ (Appendix E). 

Finally, we demonstrate that many parameter errors in the Hamiltonian model used to design the gate can also be corrected using closed-loop feedback from the experiment within the same low-rank subspace. As an example, we consider the Zeeman splitting to the unwanted _|r_<sup>_′_</sup> _⟩_ Rydberg level, ∆ _r_ . The gate is designed for ∆ _r_ = 2 _._ 69 Ω0, and is quite sensitive to variations in this parameter as a non-trivial amount of population is excited to _|r_<sup>_′_</sup> _⟩_ from _|_ 0 _⟩_ during the gate (as shown in Fig. 3c). To mimic a calibration error in this parameter, we deliberately lower the magnetic field while adjusting the laser frequency to match the _|_ 1 _⟩↔|r⟩_ transition. While the gate error is substantially increased by the parameter change, applying the same optimization protocol with the original Hessian eigenvectors recovers most of the lost fidelity (Fig. 5a). The optimized waveform is significantly different from the nominal waveform (Fig. 5b). In the case of the largest deviation, the optimization requires more than one round to converge. This multi-round behavior is consistent with numerical calculations: at this level of miscalibration, the principal space has shifted appreciably from that computed at the nominal field, pushing the correction somewhat beyond the strictly perturbative regime. The nominal Hessian directions therefore remain useful sensitive directions, but are no longer optimally aligned with the local error response. A detailed theory of which types of errors can be corrected this way is presented in Appendix D. 

### **III. DISCUSSION AND CONCLUSION** 

The low-rank Hessian optimization approach presented here is based on leading-order perturbation theory, and its effectiveness therefore requires that the initial distortion is not too large. In simulations, we find that the convergence region is reasonably large: using random initial distortions with different amplitudes and shapes, the method can reliably recover gate errors below 10<sup>_−_5</sup> after several cycles even when the initial error is as high as _∼_ 10<sup>_−_1</sup> . 

A complementary approach to calibrating optimal control gates is to directly measure the pulse errors and pre-compensate them. This has been demonstrated for neutral atoms [19] and is extensively used for superconducting qubits [45, 46]. This approach has the benefit of not relying on the qubits for feedback, but is subject to measurement and modeling errors. In the present work, we do not apply any pre-compensation; instead, we start from the initially implemented waveform and directly optimize based on the measured gate fidelity. We nevertheless expect the two methods to be complementary: direct waveform feedback can bring a strongly distorted pulse into the perturbative regime, after which low-rank Hessian optimization can efficiently correct the remaining errors. 

We now discuss how to further improve the gate. In the present geometry, unwanted coupling to the additional Rydberg state _|r_<sup>_′_</sup> _⟩_ complicates the dynamics, adds error channels, and increases the number of calibration directions. A larger magnetic field together with a more favorable laser-polarization geometry would allow a nearly pure _σ_<sup>_−_</sup> drive, suppressing this extra coupling and bringing the gate closer to the ideal three-level picture. In this regime, our model predicts that a time-optimal gate driven at Ω= 2 _π ×_ 14 MHz, together with modest improvements in atomic temperature and laser-intensity noise, can reach fidelities above 0 _._ 999, with more than 90% of the remaining error appearing as leakage. This requires increasing the laser intensity by a factor of 2.7. 

Finally, we emphasize that the low-rank Hessian theory and optimization protocol should be broadly applicable to other gates and other types of qubits. It may be particularly applicable to solid-state qubits, which suffer from large control signal distortion from long cryogenic signal chains and qubit-to-qubit variation in Hamiltonian parameters from device fabrication uncertainty. 

### **IV. ACKNOWLEDGMENTS** 

We acknowledge Yiyi Li, Michael Peper, Yicheng Bao, Pranav Mathur, Matteo Bergonzoni and Guido Pupillo for helpful conversations. This work was supported by the Army Research Office (W911NF-24-10358), DARPA MeasQuIT (HR00112490363), the Office of Naval Research (N00014-23-1-2621, N00014-26-1-2102), and the National Science Foundation through the CAREER program (PHY-2047620) and the Center for Robust Quan- 

7 

tum Simulation (OMA-2120757). 

_Note:_ While completing this work, we became aware of complementary work on high-fidelity neutral atom gates [47]. 

### **Appendix A: Experimental methods** 

We generate an array of 40 spatial-light-modulator (SLM)-defined tweezers that are loaded from a threedimensional magneto-optical trap (MOT) operating on the<sup>1</sup> _S_ 0 _→_<sup>3</sup> _P_ 1 transition. The SLM tweezer array is divided into a storage zone and a gate zone, with the latter consisting of 10 traps illuminated by a tightly focused 302 nm UV gate laser (see Fig. A1). A crossed acoustooptic deflector (AOD) tweezer array is used to dynamically move atoms between the SLM traps. This enables the preparation of defect-free arrays and the transport of atoms to and from the gate zone during an experimental sequence. Details of the experimental chamber [48], the SLM tweezer array, and the AOD-controlled moving tweezer array [37] are described in previous work. The qubits are initialized in the two nuclear-spin states of the metastable 6 _s_ 6 _p_<sup>3</sup> _P_ 0 manifold by optically pumping atoms from the ground state, as described in Ref. [19]. Qubit readout is performed using a three-outcome measurement, which is adapted from Ref. [42] and discussed in more detail in Appendix F. 

In this work, we begin each experimental sequence by preparing a set of five dimers, which are then moved to the gate zone for the single- and two-qubit gates presented in the main text. In the gate zone, the two atoms within each dimer are separated by 2.0 _µ_ m, while neighboring dimers are separated by 25 _µ_ m. The CZ gates are driven by a tightly focused 302 nm laser, with a 1 _/e_<sup>2</sup> radius _w_ 0 = 12 _µ_ m, that couples the _|_ 1 _⟩_ state to the Rydberg state _|r⟩≡|ν_ = 52 _._ 3 _, F_ = 1 _/_ 2 _, mF_ = _−_ 1 _/_ 2 _⟩_ . The UV light is generated by nonlinear frequency conversion of amplified fiber-laser sources (Fig. A2). We 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-06.png)


<!-- Start of picture text -->
6 μm<br>302 nm<br>2 μm<br>zone<br>Storage<br>zone Gate<br><!-- End of picture text -->

FIG. A1. **Average fluorescence image of the atomic array.** The array is divided into a storage zone and a gate zone (see text). The quantization axis _⃗B_ is perpendicular to the 302 nm beam. 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-08.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-09.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-10.png)


<!-- Start of picture text -->
SHG to 986 nm<br><!-- End of picture text -->


![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-11.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-12.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-13.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-14.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-15.png)


<!-- Start of picture text -->
1560 nm SFG to 604 nm<br><!-- End of picture text -->


![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-16.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-17.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-18.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-19.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-20.png)


<!-- Start of picture text -->
AOM<br>604 nm<br><!-- End of picture text -->


![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-21.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-22.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-23.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-24.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-25.png)


<!-- Start of picture text -->
Doubling Cavity<br><!-- End of picture text -->

FIG. A2. **Optical setup for generating 302 nm light.** The 302 nm light used for Rydberg excitation is generated from amplified 1971 nm and 1560 nm fiber-laser sources through SHG, SFG, and cavity-enhanced frequency doubling. 

first frequency-double a 1971 nm laser (Precilasers) to 986 nm using two periodically poled lithium niobate (PPLN) second-harmonic generation (SHG) crystals in series to increase the available 986 nm power. This light is then combined with 1560 nm light (Precilasers) in a sum-frequency generation stage, producing 604 nm light. Finally, the 604 nm light is frequency doubled in an enhancement cavity (Toptica), generating the 302 nm light used for Rydberg excitation. 

### **Appendix B: The general theory of low-rank fidelity Hessians** 

In this section, we introduce the general theory underlying the low-rank Hessian structure of gate fidelity. Consider a quantum gate generated by an ideal Hamiltonian _H_ 0( _t_ ) over the time interval _t ∈_ [0 _, T_ ]. This Hamiltonian gives an ideal unitary evolution _U_ 0( _t_ ), with _U_ 0( _T_ ) implementing the desired gate. We now suppose that control distortions perturb the system through a set of control channels, so that the Hamiltonian becomes 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0007-30.png)


where _Oµ_ ( _t_ ) are operators describing how each distortion channel couples to the system, and the real functions _sµ_ ( _t_ ) specify the corresponding distortion waveforms. The perturbed Hamiltonian generates the actual evolution _U_ ( _t_ ). 

8 

Then the interaction-picture evolution operator, 

the Dyson expansion can be written compactly as 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-03.png)


removes the ideal evolution and describes the error accumulated from the control distortions. Taking ¯ _h_ = 1, and defining 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-05.png)


where 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-07.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-08.png)


The gate fidelity is determined by the final interactionpicture evolution _UI_ ( _T_ ). Since the ideal gate has been removed in this frame, a perfect implementation corresponds to _UI_ ( _T_ ) = 1 within the computational subspace. In general, the full Hilbert space contains both the _d_ - dimensional computational subspace and additional noncomputational states. Let _P_ be the projector onto the computational subspace, and let _Q_ = 1 _− P_ project onto the leakage space. The average gate fidelity is 

Because _UI_ ( _T_ ) is generated by the distortion waveforms _sµ_ ( _t_ ), the gate fidelity is a functional of these waveforms, which we denote by _F_ [ _{sµ}_ ]. Substituting the Dyson expansion of Eqs. (B4) and (B5), and keeping terms up to second order gives 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-11.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-12.png)


The Hessian kernel _Hµν_ ( _t_ 1 _, t_ 2) is written in terms of 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-14.png)


Here _O_<sup>˜</sup> _µ_ ( _t_ ) is the traceless part of _Oµ,I_ ( _t_ ) within the computational subspace, while _Lµ_ ( _t_ ) describes the coupling between the leakage and computational subspaces. 

To interpret Eq. (B7), it is useful to view it as the continuous-waveform analogue of an ordinary finitedimensional quadratic form. The collection of distortion waveforms _{sµ_ ( _t_ ) _}_ plays the role of a vector _⃗s_ . If there are _Nc_ control channels, then _⃗s_ lives in the direct sum of _Nc_ waveform spaces, one for each value of _µ_ . The pair ( _µ, t_ ) is therefore analogous to a single vector index. Similarly, _Hµν_ ( _t_ 1 _, t_ 2) plays the role of a matrix element, with ( _µ, t_ 1) and ( _ν, t_ 2) labeling its two indices. In this 

notation, Eq. (B7) has the same structure as 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-18.png)


except that the sums over vector indices are replaced by sums over control channels and integrals over time. Thus, the basic structure is the familiar quadratic form, but now in an infinite-dimensional waveform space. 

This analogy also allows us to define Hessian eigendirections in the same way as for an ordinary matrix. The Hessian kernel can be diagonalized through the integral eigenvalue problem 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0008-21.png)


The eigenfunction _⃗vi_ = _{vi,µ_ ( _t_ ) _}_ is therefore an eigendirection in the waveform-distortion space, while the eigenvalue _λi_ gives the second-order sensitivity of the fidelity 

9 

along that direction. The rank of the Hessian kernel is defined analogously as the number of nonzero eigenvalues, or equivalently the number of independent eigendirections with nonzero sensitivity. 

orthonormal basis _{|n⟩}_<sup>_D_</sup> _n_ =1<sup>forthefullHilbertspace,</sup> with _|_ 1 _⟩ , . . . , |d⟩_ spanning the computational subspace and _|d_ + 1 _⟩ , . . . , |D⟩_ spanning the leakage subspace. Expanding the traces in Eq. (B8) gives 

To see why this Hessian has finite rank, choose an 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0009-04.png)


Here we have defined the waveform-space channel vectors _χ_<sup>coh</sup> _mn,µ_<sup>(</sup><sup>_t_)=</sup><sup>_⟨m|O_˜</sup><sup>_µ_(</sup><sup>_t_)</sup><sup>_|n⟩_and</sup><sup>_χ_leak</sup> _mℓ,µ_<sup>(</sup><sup>_t_)=</sup><sup>_⟨m| Oµ,I_(</sup><sup>_t_)</sup><sup>_|ℓ⟩_,</sup> whose components are labeled by the control channel _µ_ and time _t_ . Substituting these expressions into Eq. (B8), the Hessian kernel is a finite sum of outer products of these vectors, or schematically 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0009-06.png)


This outer-product form makes the finite-rank structure straightforward. For any input waveform _⃗s_ , the output _H⃗s_ lies in the span of the channel vectors _⃗χ_<sup>coh</sup> _mn_<sup>and</sup><sup>_⃗χ_leak</sup> _mℓ_<sup>.</sup> Conversely, any waveform orthogonal to this span has zero overlap with every outer-product term and therefore lies in the null space of the Hessian. The Hessian rank is therefore bounded by the number of independent real directions contained in these channel vectors. 

To obtain an explicit upper bound, we now count the number of independent real directions. The diagonal coherent vectors _χ_<sup>coh</sup> _mm,µ_<sup>(</sup><sup>_t_)arerealby Hermiticity of</sup><sup>_O_˜</sup><sup>_µ_(</sup><sup>_t_)</sup> and correspond to phase errors on the computational states. Because _O_<sup>˜</sup> _µ_ ( _t_ ) is traceless within the computational subspace [Eq. (B9)], 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0009-09.png)


Thus only _d −_ 1 phase-error channels are independent; the missing direction is the global phase, which does not affect the gate fidelity. 

The off-diagonal coherent vectors _χ_<sup>coh</sup> _mn,µ_<sup>(</sup><sup>_t_)describe</sup> mixing between computational states. Since _χ_<sup>coh</sup> _nm_<sup>=</sup> _χ_<sup>coh</sup> _mn_<sup>_∗_,eachpair</sup><sup>_m<n_givesonecomplexchannel,or</sup> two real directions, contributing at most _d_ ( _d −_ 1) to the Hessian rank. The leakage vectors _χ_<sup>leak</sup> _mℓ,µ_<sup>(</sup><sup>_t_) are also com-</sup> plex; there are _d_ ( _D − d_ ) such channels, contributing at most 2 _d_ ( _D − d_ ) real directions. 

Combining these contributions, the Hessian rank is bounded by 

rank( _H_ ) _≤_ ( _d −_ 1)+ _d_ ( _d −_ 1)+2 _d_ ( _D − d_ ) = 2 _dD − d_<sup>2</sup> _−_ 1 _._ (B17) 

The principal space _V_ defined in the main text is therefore the real span of these channel vectors, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0009-15.png)


If the full Hilbert space is the computational space, _D_ = _d_ , this reduces to the general bound rank( _H_ ) _≤ D_<sup>2</sup> _−_ 1 in the main text and Refs. [26, 27]. This unitary-fidelity result should be distinguished from previous Hessian-rank bounds for state-transfer fidelities, where the objective is sensitive only to errors in a single target state and the Hessian rank is correspondingly much smaller, bounded by 2( _D −_ 1) [24, 25]. 

The above derivation also gives a useful physical interpretation of how waveform distortions affect the gate. The channel vectors _⃗χ_<sup>coh</sup> _mn_<sup>and</sup><sup>_⃗χ_leak</sup> _mℓ_ are essentially the waveform kernels that determine the corresponding matrix elements of the first-order error operator _K_ 1( _T_ ) in Eq. (B4). Schematically, the relevant part of the interaction-picture evolution can be written as 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0009-18.png)


where _⃗χmn_ denotes the waveform-space vector associated with the matrix element _χmn,µ_ ( _t_ ) = _⟨m| Oµ,I_ ( _t_ ) _|n⟩_ . It can be shown that, to leading order, the correction to the fidelity is determined entirely by the relevant matrix elements of _K_ 1( _T_ ): diagonal computational-subspace elements give phase-error channels, off-diagonal computational-subspace elements give mixing channels, and computational–leakage elements give leakage channels. Evolution entirely within the leakage subspace does not contribute at this order because the system starts in the computational subspace. This formalism will also be useful for understanding which Hamiltonian errors can be corrected by waveform optimization, as illustrated more explicitly in Appendix D. 

10 

### **Appendix C: Rank counting and fidelity decomposition** 

Eq. (B17) gives a general finite bound on the rank of the fidelity Hessian. In specific systems, however, this bound can be loose because symmetries and selection rules eliminate many error channels. A tighter bound can often be obtained by identifying the independent physical error channels and applying the same rank-counting logic: 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-03.png)


where _N_ phase counts independent real phase-error channels, while _N_ mixing and _N_ leakage count independent complex mixing and leakage channels, respectively. 

For example, in the three-level CZ model shown in Fig. 1a and b, there is no mixing between different computational states. The only independent leakage channels are 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-06.png)


with the _|_ 10 _⟩↔|r_ 0 _⟩_ channel related to the first one by symmetry, while _|_ 00 _⟩_ is uncoupled. Each leakage channel contributes at most two real Hessian directions. After removing the freely tunable single-qubit phase, the only remaining phase-error channel is the controlled phase, _φ_ 11 _−_ 2 _φ_ 01, whose target value is _π_ . Thus this model has at most five nonzero Hessian directions: four from the two leakage channels and one from the controlled-phase channel. 

For the more complicated AR CZ gate shown in Fig. 3a and b, there is still no mixing between different computational states. However, the independent leakage channels are now 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-09.png)


Here _|W_<sup>_′_</sup> _⟩_ = ( _|_ 0 _r_<sup>_′_</sup> _⟩_ + _|r_<sup>_′_</sup> 0 _⟩_ ) _/√_ 2 is the analogous symmetric leakage state. These four complex leakage channels contribute at most eight real Hessian directions. For the phase channels, the phase of _|_ 00 _⟩_ can be taken as an irrelevant global phase. In this particular implementation, we choose to fix the relative phases of both _|_ 01 _⟩_ and _|_ 11 _⟩_ , leaving two independent relative phase channels. Therefore, the total Hessian rank is bounded by 4 _×_ 2 + 2 = 10. 

We now specialize to the AR CZ gate and show how the abstract channel picture appears in the leakage and phase contributions to the fidelity. In this model, the ideal Hamiltonian _H_ 0( _t_ ) has the form 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-12.png)


where Ω0( _t_ ) and _ϕ_ 0( _t_ ) are the ideal amplitude and phase waveforms. Including the polarization and Clebsch– Gordan coefficients, the raising operator is 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-14.png)


To describe waveform distortions, we follow Eq. (B1) and perturb the ideal Hamiltonian in the two drive quadratures: 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-16.png)


where _sx_ ( _t_ ) and _sy_ ( _t_ ) describe distortions in the two drive quadratures. In this convention, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-18.png)


The factor Ω0( _t_ ) is included so that the distortion is tapered by the ideal pulse envelope and vanishes when the ideal laser amplitude is zero. With the ideal Hamiltonian and perturbation operators specified, the Hessian kernel follows directly from Eq. (B8). The eigendirections are obtained by solving the integral eigenproblem in Eq. (B12), which can be done numerically after discretizing the waveform space, for example in a time-bin basis. The eigenspectrum and corresponding eigenvectors are illustrated in Fig. A3a,b. 

To interpret these eigendirections physically, we now rewrite the same leading-order fidelity loss in terms of leakage and phase errors. Since the AR CZ dynamics do not mix different computational states, the ideal evolution within the computational subspace _{_ 00 _,_ 01 _,_ 10 _,_ 11 _}_ is diagonal, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-21.png)


with the CZ condition _φ_ 11 _−_ 2 _φ_ 01 + _φ_ 00 = _π_ . Using the interaction-picture error unitary of Eq. (B2), and removing the common phase of the _|_ 00 _⟩_ sector, its computational-subspace projection can be parameterized as 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0010-23.png)


Here, _θ_ 01 and _θ_ 11 are residual phase errors relative to the _|_ 00 _⟩_ sector, while _α_ 00, _α_ 01, and _α_ 11 describe the reduction of the return amplitude in each sector. Substituting 

this form into the average gate fidelity and expanding to 

11 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-01.png)


<!-- Start of picture text -->
a b<br>v 1 v 2 v 3 v 4 v 5 v 6 v 7<br>3.5 1<br>3.0 0<br>1.0<br>2.5 0.5<br>2.0 0.0<br>1.5 v 8 v 9 v 10 v 11 v 12 v 13 v 14<br>1<br>1.0<br>0<br>0.5 1.0<br>0.0 0.5<br>1 3 5 7 9 11 13 0.0<br>Mode index  i<br>t<br>2|0<br>|Ω/Ω<br>)<br>π<br>λi /(2<br>ϕ<br>2|0<br>Eigenvalue<br>|Ω/Ω<br>)<br>π<br>/(2<br>ϕ<br><!-- End of picture text -->

FIG. A3. **Eigenspectrum and eigenvectors of the AR gate fidelity Hessian.** (a) Computed eigenvalues of the 10 principal Hessian modes, together with 4 representative null-space modes. (b) Intensity _|_ Ω( _t_ ) _/_ Ω0 _|_<sup>2</sup> and phase profile _ϕ_ ( _t_ ) of the AR CZ gate distorted along each eigendirection _⃗vi ≡{vi,x_ ( _t_ ) _, vi,y_ ( _t_ ) _}_ corresponding to the eigenvalues in (a), with _T_ normalization �0<sup>(</sup><sup>_v_</sup> _i,x_<sup>2+</sup><sup>_v_</sup> _i,y_<sup>2) d</sup><sup>_t_=1.Thedistortionstrengthis</sup><sup>_ϵ_=0</sup><sup>_._6,with</sup><sup>_s_</sup> _x/y_<sup>(</sup><sup>_t_)=</sup><sup>_ϵv_</sup> _i,x/y_<sup>(</sup><sup>_t_)inEq.(C5).Thelightgray</sup> lines indicate the gate pulse without distortion. 

leading nonvanishing order gives 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-04.png)



![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-05.png)


This separates the infidelity into leakage from _|_ 00 _⟩_ , leakage from the symmetric _|_ 01 _⟩_ and _|_ 10 _⟩_ sectors, leakage from _|_ 11 _⟩_ , and residual coherent phase error _ϵθ_ . 

We can connect the _α_ and _θ_ parameters back to the first-order channels _⃗χ_ in _K_ 1( _T_ ), introduced in Appendix B. It can be shown by expanding the sector return amplitude, (1 _− αq_ ) _e_<sup>_iθq_</sup> , and comparing it with the Dyson-series expansion in Eqs. (B4) and (B5), that _θ_ is determined by the relative diagonal coherent channels, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-08.png)


while _α_ is determined by the squared first-order leakage amplitudes, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-10.png)


For the AR CZ gate, the relevant leakage sets are 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-12.png)


The experimentally meaningful quantities _α_ and _θ_ therefore provide a physical parameterization of the same channel vectors that determine the Hessian in Eq. (B15). This example also clarifies what we mean by a leakage channel: it is not specified by the initial computational sector alone, but by the transition from that sector to a 

particular leakage state. Thus the _|_ 01 _⟩_ sector contains two independent leakage channels, to _|_ 0 _r⟩_ and _|r_<sup>_′_</sup> 1 _⟩_ . 

Equation (C9) shows that the AR CZ infidelity induced by a waveform distortion separates into three leakage contributions and one coherent phase contribution. Since each contribution is quadratic in the distortion to leading order, the curvature along each normalized Hessian eigendirection can be decomposed in the same way, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0011-16.png)


For each eigendirection, these four terms can be computed by substituting the corresponding distortion mode into the leakage and phase expressions above. This is the decomposition shown in Fig. 3e of the main text. 

Experimentally, we independently measure the leakage amplitude _αq_ and phase shift _θq_ while scanning along each Hessian eigendirection. To extract _αq_ for a leakage channel _q_ , we prepare the corresponding initial computational state and apply repeated CZ gates, with each gate followed by autoionization to measure the population leaked out of the computational subspace. To measure _θq_ , we prepare a superposition of the relevant computational states and perform Ramsey sequences with multiple inserted CZ gates. We then use Eqs. (C9) and (C10) to convert the measured _αq_ and _θq_ into the predicted sensitivity, and compare the result with the directly measured gate sensitivity. 

### **Appendix D: Correction for Hamiltonian errors** 

The previous Appendices B and C focused on waveform distortions. The same first-order channel picture also gives a simple criterion for when the Hessian-based scan can correct other Hamiltonian errors. 

12 

Consider an implemented Hamiltonian consisting of the ideal control Hamiltonian, a waveform correction, and an additional small Hamiltonian perturbation: 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0012-02.png)


Here, the correction waveform is restricted to the scanned Hessian eigendirections in the principal space, _s_ =<sup>�</sup> _i_<sup>_ci⃗vi_.Usingthesameperturbativeexpansionas</sup> in Eq. (B4), the first-order error generator is linear in both the waveform correction and the additional Hamiltonian perturbation: 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0012-04.png)


Here, _K_ 1<sup>(</sup><sup>_i_)(</sup><sup>_T_)isthefirst-ordergeneratorobtainedby</sup> setting the waveform distortion to _⃗vi_ , while _K_ 1<sup>(</sup><sup>_p_)(</sup><sup>_T_)is</sup> generated by the perturbation _Hp_ ( _t_ ), 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0012-06.png)


Therefore, the Hamiltonian error can be cancelled to first order using only the scanned eigendirections if, for the relevant channels connected to the computational subspace, 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0012-08.png)


Equivalently, the perturbation must generate only firstorder phase, mixing, or leakage channels already accessible through the scanned Hessian directions. If it introduces a new channel outside this span, the restricted optimization cannot remove the leading-order error without adding new control directions. 

For the AR CZ gate, the first-order correctable space is spanned by the four complex leakage channels and two real phase channels (Appendix C). A laser-detuning error provides the simplest correctable example: it is equivalent to an error in the phase chirp of the drive and therefore does not change the channel structure. A less trivial example is an error in the calibrated ratio between the Rydberg-state Zeeman splitting ∆ _r_ and the UV Rabi frequency Ω0. For a fractional error in the splitting between _|r⟩_ and _|r_<sup>_′_</sup> _⟩_ , the perturbation can be written as 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0012-11.png)


This perturbation is not itself one of the laser-control quadratures, so its correctability is not guaranteed from the control Hamiltonian alone. However, it does not introduce new first-order error channels; it only changes the weights of the existing phase and leakage channels. It is therefore correctable to leading order by the same Hessian scan, as demonstrated in the main text. In contrast, a perturbation that couples to a new leakage state, or one that introduces mixing between computational states, generally produces new first-order channels and cannot be fully corrected without enlarging the control space. 

### **Appendix E: Error model for CZ gates** 

To understand the sources of gate infidelity in our twoqubit gates, we develop a numerical model similar to that used in Refs. [19, 33]. The simulation is primarily based on the four-level _{_ 0 _,_ 1 _, r, r_<sup>_′_</sup> _}_ model discussed above, and combines a master-equation treatment with Monte Carlo sampling. The parameters used in the model are determined from independent experiments, while the simulated gate pulse is the designed waveform in Fig. 3b. 

We measure the Rydberg-state lifetime to be _Tr_ = 42(2) _µ_ s by exploiting the ability to trap Rydberg atoms in ytterbium [49]. This finite lifetime contributes _ε_ raw = 3 _._ 1 _×_ 10<sup>_−_3</sup> to the raw gate infidelity. Most of this error, however, appears as leakage out of the qubit subspace: we separately measure that about 90% of the Rydberglifetime-induced errors leave the qubit subspace. As a result, after postselection on no detected loss, this contribution is reduced to _ε_ ps = 1 _._ 2 _×_ 10<sup>_−_4</sup> . 

Another important contribution comes from the Doppler effect, which contributes _ε_ raw = 3 _._ 7 _×_ 10<sup>_−_4</sup> to the raw infidelity for an atomic temperature of _T_ = 2 _._ 7 _µ_ K. In our numerical model, Doppler dephasing is the largest remaining in-subspace contribution, giving a postselected error of _ε_ ps = 2 _._ 8 _×_ 10<sup>_−_4</sup> . 

Finite Rydberg blockade within each addressed dimer provides an additional contribution. The gate pulse is designed in the perfect-blockade limit and is not explicitly compensated for finite interaction strength. At the nominal spacing _R_ = 2 _._ 0 _µ_ m, the interaction already starts to deviate from the simple van der Waals regime and enters the crossover toward the F¨orster-interaction regime. To capture this effect, we use a separate _R_ - dependent model based on Rydberg-pair eigenstates calculated using the multichannel quantum defect theory (MQDT) model of Ref. [33]. In this model, for each interatomic distance _R_ , the pair-state Hamiltonian is written in the MQDT eigenbasis, and the laser couplings are computed from the overlaps with the original productstate basis. At the nominal spacing, this model gives a finite-blockade contribution of _ε_ raw = 1 _._ 6 _×_ 10<sup>_−_4</sup> and _ε_ ps = 3 _×_ 10<sup>_−_5</sup> . 

On top of this nominal finite-blockade error, the interatomic spacing also fluctuates shot to shot because of the finite temperature of the atoms. We therefore average the simulated gate fidelity over the thermal distribution of interatomic distances. The radial temperature is inferred from Doppler-sensitive Ramsey measurements, while the axial temperature is constrained by comparing measured Rydberg pair-loss spectra with MQDT-based simulations. This comparison is consistent with using _T_ = 2 _._ 7 _µ_ K in both the radial and axial directions, giving an additional contribution from interatomic-distance fluctuations of _ε_ raw = 1 _._ 5 _×_ 10<sup>_−_4</sup> and _ε_ ps = 8 _×_ 10<sup>_−_5</sup> . 

Laser phase noise (PN) contributes a raw error of _ε_ raw = 1 _._ 4 _×_ 10<sup>_−_4</sup> and a postselected error of _ε_ ps = 1 _._ 0 _×_ 10<sup>_−_4</sup> . Laser amplitude noise (AN) contributes a smaller raw error of _ε_ raw = 1 _×_ 10<sup>_−_5</sup> , mostly through leakage. We also consider an unwanted _π_ -polarized component of 

13 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0013-01.png)


<!-- Start of picture text -->
a b c<br>5d6s 33PP 20 3 D 1 3P 1 36s6d S 1 33PP 2 3 D 2 3P 1 1P 1 3P 1<br>0<br>1S 0 1S 0 1S 0<br>Pumping Depump  Imaging<br>d<br>Three-Outcome DP DP<br>Measurement<br><!-- End of picture text -->

FIG. A4. **Three-outcome measurement.** (a,b,c) Level scheme and pulse sequence used for state preparation and readout. (a) Atoms are initialized in the metastable 6 _s_ 6 _p_<sup>3</sup> _P_ 0 manifold using optical pumping through the 5 _d_ 6 _s_<sup>3</sup> _D_ 1 state. (b) State-selective depumping transfers population in _|_ 0 _⟩_ from 3 _P_ 0 to 3 _P_ 2 using a two-photon Raman transition through 6 _s_ 7 _s_<sup>3</sup> _S_ 1, followed by depumping to 1 _S_ 0 through 6 _s_ 6 _d_<sup>3</sup> _D_ 2. (c) Atoms in<sup>1</sup> _S_ 0 are detected by fluorescence imaging on either the<sup>1</sup> _S_ 0 _↔_<sup>1</sup> _P_ 1 transition at 399 nm or the<sup>1</sup> _S_ 0 _↔_<sup>3</sup> _P_ 1 transition at 556 nm. (d) The three-outcome measurement consists of state-selective depumping of _|_ 0 _⟩_ , a first image at 399 nm, an RF _π_ pulse, a second state-selective depumping step, and a final image at 556 nm. 

the laser field, whose relative Rabi frequency is measured in a separate experiment to be Ω _π/_ Ω _σ− <_ 1 _._ 8 _×_ 10<sup>_−_3</sup> . The resulting contribution to the gate infidelity is below 10<sup>_−_5</sup> and is not shown in Fig. 4f. 

Adding these contributions gives a total simulated raw infidelity of about _ε_ raw = 4 _._ 0 _×_ 10<sup>_−_3</sup> and a postselected infidelity of about _ε_ ps = 6 _._ 6 _×_ 10<sup>_−_4</sup> . The simulated raw error agrees well with the measured value, while the measured postselected error remains slightly higher than the model prediction. We expect that this remaining discrepancy is mainly due to the difficulty of quantitatively modeling the full Rydberg interaction involving the unwanted _|r_<sup>_′_</sup> _⟩_ state. This interaction can introduce additional leakage channels, including population in _|r_<sup>_′_</sup> _r_<sup>_′_</sup> _⟩_ and in other Rydberg-pair states mixed by the interaction. Since these channels are not fully captured by the model or by the scanned Hessian eigendirections, they are not expected to be completely removed by the optimization. 

### **Appendix F: Three-Outcome Measurement** 

To initialize the atoms in the metastable<sup>3</sup> _P_ 0 state, the atoms are optically pumped through a two-photon transition from<sup>1</sup> _S_ 0 to<sup>3</sup> _D_ 1 through the intermediate state<sup>3</sup> _P_ 1, as shown in Fig. A4a. The state-selective depumping sequence [42], shown in Fig. A4b, is used to independently measure the _|_ 0 _⟩_ and _|_ 1 _⟩_ populations. In the first depumping step, atoms in _|_ 0 _⟩_ are transferred to the ground state and detected by destructive fluores- 

cence imaging on the<sup>1</sup> _S_ 0 _↔_<sup>1</sup> _P_ 1 transition at 399 nm (Fig. A4c). A subsequent _π_ pulse maps the _|_ 1 _⟩_ population onto _|_ 0 _⟩_ , after which the same depumping procedure sends the mapped population to<sup>1</sup> _S_ 0 for imaging on the 1 _S_ 0 _↔_ 3 _P_ 1 transition at 556 nm. Together, the two images define a three-outcome measurement (Fig. A4d): atoms detected in the first image are assigned to _|_ 0 _⟩_ , atoms detected in the second image are assigned to _|_ 1 _⟩_ , and atoms that are dark in both images are classified as lost. 

Depumping from _|_ 0 _⟩_ is implemented in two steps. First, a two-photon Raman transition coherently drives the population to the 6 _s_ 6 _p_<sup>3</sup> _P_ 2 manifold. A resonant depumping laser then couples this manifold to the 6 _s_ 6 _d_<sup>3</sup> _D_ 2 state, which decays to the ground state via 6 _s_ 6 _p_<sup>3</sup> _P_ 1. The Raman transition is driven through the intermediate state 6 _s_ 7 _s_<sup>3</sup> _S_ 1, _F_ = 1 _/_ 2, with a red detuning of ∆ _≃_ 2 _π ×_ 12 GHz. It is resonant with _|_ 0 _⟩→_ ��6 _s_ 6 _p_ 3 _P_ 2 _, F_ = 3 _/_ 2 _, mF_ = _−_ 1 _/_ 2�, while the corresponding transition from _|_ 1 _⟩_ is detuned by about 12 MHz through the Zeeman splitting of the 6 _s_ 6 _p_<sup>3</sup> _P_ 2 manifold. The 649 nm and 770 nm lasers have single-photon Rabi frequencies Ω649 = 2 _π ×_ 71(2) MHz and Ω770 = 2 _π ×_ 130(3) MHz, corresponding to an effective two-photon Raman Rabi frequency of Ω649+770 = 2 _π×_ 0 _._ 278(1) MHz. 

To avoid inhomogeneous light shifts during gate operations, the optical tweezers are modulated at 400 kHz [37]. Consequently, the Raman-transfer and depumping steps are synchronized to the trap-off portion of the modulation cycle. Applying the depumping sequence with the traps off also avoids atom loss due to anti-trapping of the 6 _s_ 6 _p_<sup>3</sup> _P_ 2 state. Since the finite trap-off window is shorter than the nominal Raman _π_ -pulse time, the 550 ns Raman pulse and depumping sequence are repeated 60 times to ensure efficient transfer of the _|_ 0 _⟩_ population to the ground state. 

To characterize the performance of the three-outcome measurement, we prepare atoms in either _|_ 0 _⟩_ or _|_ 1 _⟩_ and apply the full measurement sequence. The resulting photon-count distributions are shown in Fig. 2a, and the outcome probabilities are summarized in Table I. The observed infidelities include contributions from both state-preparation and measurement (SPAM) errors. 

We find that the spin-flip errors _P_ 0(1) = 0 _._ 17(1)% and _P_ 1(0) = 0 _._ 83(3)% are largely limited by off-resonant scattering of the 649 nm Raman light, which can accidentally depump population in _|_ 1 _⟩_ during the _|_ 0 _⟩_ -selective depumping sequence. We independently measure that 0 _._ 63(9)% of atoms prepared in _|_ 1 _⟩_ are depumped to<sup>1</sup> _S_ 0 during state-selective readout, in agreement with a numerical simulation giving 0 _._ 6(1)%. During readout, this process directly contributes to the misidentification of atoms prepared in _|_ 1 _⟩_ as _|_ 0 _⟩_ , since accidental depumping produces a bright signal in the first image. 

The same scattering mechanism also limits the initial spin purity during a separate spin-purification stage. In this stage, atoms are optically pumped from<sup>1</sup> _S_ 0 into the metastable manifold, with populations in _|_ 0 _⟩_ and _|_ 1 _⟩_ set by the branching ratios of the pumping sequence as 

14 

|Initial state|Outcome <br>|Experiment (%) <br>|Model (%)<br>|
|---|---|---|---|
||_P_0(0)|98.75(3)|98.67(12)|
|_|_0_⟩_|_P_0(1)|0.17(1)|0.14(7)|
||_P_0(loss)|1.07(3)|1.19(9)|
||_P_1(0)|0.83(3)|0.70(10)|
|_|_1_⟩_|_P_1(1)|97.53(5)|97.85(15)|
||_P_1(loss)|1.65(4)|1.45(13)|



TABLE I. **Comparison between the measured and modeled SPAM errors for the three-outcome stateselective readout.** 

shown in Fig. A4a. The _|_ 0 _⟩_ population is then selectively depumped back to<sup>1</sup> _S_ 0, and the cycle is repeated 120 times to accumulate population in _|_ 1 _⟩_ . However, offresonant scattering can also depump a small fraction of the desired _|_ 1 _⟩_ population back to<sup>1</sup> _S_ 0. Upon repumping, this population can enter either metastable spin state, producing a finite residual spin impurity before readout. Together, readout-induced misidentification and imperfect spin purification account for the majority of the measured spin-flip errors. 

To quantify the total SPAM infidelity, we model the full sequence using a four-state transition-matrix model that tracks the atom population in _|_ 1 _⟩_ , _|_ 0 _⟩_ ,<sup>1</sup> _S_ 0, and loss. Each elementary operation is represented by a transition matrix between these states, with transition probabilities determined from independent calibration measurements. The full model is obtained by composing the matrices for the successive steps of the sequence, yielding the expected probabilities for the three measurement outcomes. The calibrated error channels include loss during optical pumping and depumping, 0 _._ 005(1), whose microscopic origin has not yet been unambiguously identified, as well as image-classification errors for both fluorescence images. We denote false-positive errors, in which a dark atom is classified as bright, by _ϵ_ FP, and false-negative errors, in which a bright atom is classified as dark, by _ϵ_ FN. For the destructive 399 nm image, we measure _ϵ_<sup>399</sup> FP<sup>=0</sup><sup>_._0020(16)and</sup><sup>_ϵ_399</sup> FN<sup>=0</sup><sup>_._00090(21).</sup> For each 556 nm image, we measure _ϵ_<sup>556</sup> FP<sup>=3</sup><sup>_×_10</sup><sup>_−_4,</sup> _ϵ_<sup>556</sup> FN<sup>= 2</sup><sup>_×_10</sup><sup>_−_4, and an imaging-induced atom-loss prob-</sup> ability of 0 _._ 004(1). The model also accounts for the finite duration of each operation by including decay from the metastable<sup>3</sup> _P_ 0 manifold, with measured lifetime 1 _._ 50(7) s, and atom loss from the tweezer, with lifetime 25(5) s. 

A comparison between the measured and predicted probabilities is shown in Table I. Overall, the measured infidelities are consistent with the values predicted by the model, indicating that the dominant SPAM error mechanisms are captured. The three-outcome measurement is mainly limited by Raman-beam scattering and 

by errors accumulated over the finite sequence duration. Raman-beam scattering produces spin-changing SPAM errors through off-resonant depumping of the nominally dark spin state, while the finite sequence duration leads to metastable-state decay and atom loss. These mechanisms suggest several routes for improvement. Scattering-induced spin flips could be suppressed by increasing the available Raman laser power, allowing operation farther from the intermediate-state resonance while maintaining the same Raman Rabi frequency. The 3 _P_ 0 lifetime, currently limited in part by scattering from the 488 nm trapping light [19], could also be extended by using a trapping wavelength with a lower scattering rate, such as 780 nm. Finally, the sequence duration could be reduced by increasing the RF Rabi frequency beyond its present value of approximately 300 Hz, directly addressing the _|_ 1 _⟩→_ ��6 _s_ 6 _p_ 3 _P_ 2� Raman transition in the second depumping step to eliminate the RF _π_ pulse, or operating at a constant magnetic field to avoid ramping stages in the protocol [42]. 

### **Appendix G: Randomized benchmarking of CZ gates** 

For most of this work, we characterize the CZ gates using the echoed global randomized benchmarking sequence of Ref. [16], which cancels sensitivity to singlequbit phase errors while preserving the number of singlequbit operations in the sequence (Fig. A5a). The only exception is Fig. 3d, where we instead use a global randomized benchmarking sequence similar to that of Ref. [33], without the echo cancellation (Fig. A5b). This latter sequence remains sensitive to single-qubit phase errors, which we leverage to more accurately measure the fidelity response along the Hessian-sensitive directions. 

## **a** 


![](.figures/arxiv__2606.05060/2606.05060.pdf-0014-10.png)


## **b** 

FIG. A5. **Global randomized benchmarking circuits.** (a) Circuit used for echoed global randomized benchmarking. (b) Circuit used for non-echoed global randomized benchmarking, which is sensitive to single-qubit phase errors. After each CZ gate, an unshown virtual ( _Z_ ) rotation is applied by shifting the phases of all subsequent gates. 

- [1] J. P. Palao and R. Kosloff, Quantum Computing by an Optimal Control Algorithm for Unitary Transforma- 

tions, Physical Review Letters **89** , 188301 (2002). 

15 

- [2] N. Khaneja, T. Reiss, C. Kehlet, T. Schulte-Herbr¨uggen, and S. J. Glaser, Optimal control of coupled spin dynamics: design of NMR pulse sequences by gradient ascent algorithms, Journal of Magnetic Resonance **172** , 296 (2005). 

- [3] T. Caneva, T. Calarco, and S. Montangero, Chopped random-basis quantum optimization, Physical Review A **84** , 022326 (2011). 

- [4] S. Machnes, E. Ass´emat, D. Tannor, and F. K. Wilhelm, Tunable, Flexible, and Efficient Optimization of Control Pulses for Practical Qubits, Physical Review Letters **120** , 150401 (2018). 

- [5] F. K. Wilhelm, S. Kirchhoff, S. Machnes, N. Wittler, and D. Sugny, An introduction into optimal control for quantum technologies (2020), arXiv:2003.10132. 

- [6] A. Sp¨orl, T. Schulte-Herbr¨uggen, S. J. Glaser, V. Bergholm, M. J. Storcz, J. Ferber, and F. K. Wilhelm, Optimal control of coupled josephson qubits, Physical Review A **75** , 012302 (2007). 

- [7] T. Choi, S. Debnath, T. A. Manning, C. Figgatt, Z.X. Gong, L.-M. Duan, and C. Monroe, Optimal quantum control of multimode couplings between trapped ion qubits for scalable entanglement, Physical Review Letters **112** , 190502 (2014). 

- [8] P. H. Leung, K. A. Landsman, C. Figgatt, N. M. Linke, C. Monroe, and K. R. Brown, Robust 2-qubit gates in a linear ion crystal using a frequency-modulated driving force, Physical Review Letters **120** , 020501 (2018). 

- [9] M. Kang, Q. Liang, B. Zhang, S. Huang, Y. Wang, C. Fang, J. Kim, and K. R. Brown, Batch optimization of frequency-modulated pulses for robust two-qubit gates in ion chains, Phys. Rev. Appl. **16** , 024039 (2021). 

- [10] H. Levine, A. Keesling, G. Semeghini, A. Omran, T. T. Wang, S. Ebadi, H. Bernien, M. Greiner, V. Vuleti´c, H. Pichler, and M. D. Lukin, Parallel Implementation of High-Fidelity Multiqubit Gates with Neutral Atoms, Physical Review Letters **123** , 170503 (2019). 

- [11] S. Jandura and G. Pupillo, Time-Optimal Two- and Three-Qubit Gates for Rydberg Atoms, Quantum **6** , 712 (2022). 

- [12] C. Fromonteil, D. Bluvstein, and H. Pichler, Protocols for Rydberg Entangling Gates Featuring Robustness against Quasistatic Errors, PRX Quantum **4** , 020335 (2023). 

- [13] S. Jandura, J. D. Thompson, and G. Pupillo, Optimizing Rydberg Gates for Logical-Qubit Performance, PRX Quantum **4** , 020336 (2023). 

- [14] N. Glaser, F. Roy, I. Tsitsilin, L. Koch, N. Bruckmoser, J. Schirk, J. Romeiro, G. Huber, F. Wallner, M. Singh, G. Krylov, A. Marx, L. S¨odergren, C. Schneider, M. Werninghaus, and S. Filipp, Closed-loop optimization for high-fidelity controlled- _z_ gates in superconducting qubits, Phys. Rev. Appl. **24** , 024048 (2025). 

- [15] L. S. Theis, F. Motzoi, F. K. Wilhelm, and M. Saffman, High-fidelity Rydberg-blockade entangling gate using shaped, analytic pulses, Physical Review A **94** , 032306 (2016). 

- [16] S. J. Evered, D. Bluvstein, M. Kalinowski, S. Ebadi, T. Manovitz, H. Zhou, S. H. Li, A. A. Geim, T. T. Wang, N. Maskara, H. Levine, G. Semeghini, M. Greiner, V. Vuleti´c, and M. D. Lukin, High-fidelity parallel entangling gates on a neutral-atom quantum computer, Nature **622** , 268 (2023). 

- [17] J. A. Muniz, M. Stone, D. T. Stack, M. Jaffe, J. M. Kindem, L. Wadleigh, E. Zalys-Geller, X. Zhang, C.-A. 

   - Chen, M. A. Norcia, J. Epstein, E. Halperin, F. Hummel, T. Wilkason, M. Li, K. Barnes, P. Battaglino, T. C. Bohdanowicz, G. Booth, A. Brown, M. O. Brown, W. B. Cairncross, K. Cassella, R. Coxe, D. Crow, M. Feldkamp, C. Griger, A. Heinz, A. M. W. Jones, H. Kim, J. King, K. Kotru, J. Lauigan, J. Marjanovic, E. Megidish, M. Meredith, M. McDonald, R. Morshead, S. Narayanaswami, C. Nishiguchi, T. Paule, K. A. Pawlak, K. L. Pudenz, D. R. P´erez, A. Ryou, J. Simon, A. Smull, M. Urbanek, R. J. M. van de Veerdonk, Z. Vendeiro, T.-Y. Wu, X. Xie, and B. J. Bloom, HighFidelity Universal Gates in the 171Yb Ground-State Nuclear-Spin Qubit, PRX Quantum **6** , 020334 (2025). 

- [18] J. Kelly, R. Barends, B. Campbell, Y. Chen, Z. Chen, B. Chiaro, A. Dunsworth, A. G. Fowler, I.-C. Hoi, E. Jeffrey, A. Megrant, J. Mutus, C. Neill, P. J. J. O’Malley, C. Quintana, P. Roushan, D. Sank, A. Vainsencher, J. Wenner, T. C. White, A. N. Cleland, and J. M. Martinis, Optimal Quantum Control Using Randomized Benchmarking, Physical Review Letters **112** , 240504 (2014). 

- [19] S. Ma, G. Liu, P. Peng, B. Zhang, S. Jandura, J. Claes, A. P. Burgers, G. Pupillo, S. Puri, and J. D. Thompson, High-fidelity gates and mid-circuit erasure conversion in an atomic qubit, Nature **622** , 279 (2023). 

- [20] M. Werninghaus, D. J. Egger, F. Roy, S. Machnes, F. K. Wilhelm, and S. Filipp, Leakage reduction in fast superconducting qubit gates via optimal control, npj Quantum Information **7** , 14 (2021). 

- [21] V. V. Sivak, A. Eickbusch, H. Liu, B. Royer, I. Tsioutsios, and M. H. Devoret, Model-Free Quantum Control with Reinforcement Learning, Physical Review X **12** , 011059 (2022). 

- [22] R. Porotti, V. Peano, and F. Marquardt, GradientAscent Pulse Engineering with Feedback, PRX Quantum **4** , 030305 (2023). 

- [23] J. L. White, B. J. Pearson, and P. H. Bucksbaum, Extracting quantum dynamics from genetic learning algorithms through principal control analysis, Journal of Physics B: Atomic, Molecular and Optical Physics **37** , L399 (2004). 

- [24] H. Rabitz, T.-S. Ho, M. Hsieh, R. Kosut, and M. Demiralp, Topology of optimally controlled quantum mechanical transition probability landscapes, Physical Review A **74** , 012721 (2006). 

- [25] Z. Shen, M. Hsieh, and H. Rabitz, Quantum optimal control: Hessian analysis of the control landscape, The Journal of Chemical Physics **124** , 204106 (2006). 

- [26] T.-S. Ho, J. Dominy, and H. Rabitz, Landscape of unitary transformations in controlled quantum dynamics, Physical Review A **79** , 013422 (2009). 

- [27] E. Berger, V. Maurya, Z. M. McIntyre, K. X. Wei, H. Haas, and D. Puzzuoli, Dimensionality reduction for closed-loop quantum gate calibration (2024), arXiv:2412.05230. 

- [28] D. Jaksch, J. I. Cirac, P. Zoller, S. L. Rolston, R. Cˆot´e, and M. D. Lukin, Fast Quantum Gates for Neutral Atoms, Physical Review Letters **85** , 2208 (2000). 

- [29] L. Isenhower, E. Urban, X. Zhang, A. Gill, T. Henage, T. A. Johnson, T. Walker, and M. Saffman, Demonstration of a neutral atom controlled-not quantum gate, Physical Review Letters **104** , 010503 (2010). 

- [30] T. Wilk, A. Ga¨etan, C. Evellin, J. Wolters, Y. Miroshnychenko, P. Grangier, and A. Browaeys, Entanglement of two individual neutral atoms using rydberg blockade, 

16 

Physical Review Letters **104** , 010502 (2010). 

- [31] M. Saffman, I. Beterov, A. Dalal, E. P´aez, and B. Sanders, Symmetric rydberg controlled-z gates with adiabatic pulses, Physical Review A **101** , 062309 (2020). 

- [32] A. Pagano, S. Weber, D. Jaschke, T. Pfau, F. Meinert, S. Montangero, and H. P. B¨uchler, Error budgeting for a controlled-phase gate with strontium-88 Rydberg atoms, Physical Review Research **4** , 033019 (2022). 

- [33] M. Peper, Y. Li, D. Y. Knapp, M. Bileska, S. Ma, G. Liu, P. Peng, B. Zhang, S. P. Horvath, A. P. Burgers, and J. D. Thompson, Spectroscopy and Modeling of<sup>171</sup> Yb Rydberg States for High-Fidelity Two-Qubit Gates, Physical Review X **15** , 011009 (2025). 

- [34] J. W. Lis, A. Senoo, W. F. McGrew, F. R¨onchen, A. Jenkins, and A. M. Kaufman, Midcircuit Operations Using the omg Architecture in Neutral Atom Arrays, Physical Review X **13** , 041035 (2023). 

- [35] Y. Wu, S. Kolkowitz, S. Puri, and J. D. Thompson, Erasure conversion for fault-tolerant quantum computing in alkaline earth Rydberg atom arrays, Nature Communications **13** , 4657 (2022). 

- [36] K. Sahay, J. Jin, J. Claes, J. D. Thompson, and S. Puri, High-threshold codes for neutral-atom qubits with biased erasure errors, Physical Review X **13** , 041013 (2023). 

- [37] B. Zhang, G. Liu, G. Bornet, S. P. Horvath, P. Peng, S. Ma, S. Huang, S. Puri, and J. D. Thompson, Leveraging erasure errors in logical qubits with metastable 171Yb atoms (2025), arXiv:2506.13724. 

- [38] H. Perrin, S. Jandura, and G. Pupillo, Quantum Error Correction resilient against Atom Loss, Quantum **9** , 1884 (2025). 

- [39] G. Baranes, M. Cain, J. P. B. Ataides, D. Bluvstein, J. Sinclair, V. Vuleti´c, H. Zhou, and M. D. Lukin, Leveraging Qubit Loss Detection in Fault-Tolerant Quantum Algorithms, Physical Review X **16** , 011002 (2026). 

- [40] C.-C. Yu, Z.-H. Chen, Y.-H. Deng, C.-Y. Lu, M.C. Chen, and J.-W. Pan, Taming rydberg decay with measurement-based quantum computation, Physical Review Letters **136** , 160601 (2026). 

- [41] D. Bluvstein, A. A. Geim, S. H. Li, S. J. Evered, J. P. Bonilla Ataides, G. Baranes, A. Gu, T. Manovitz, M. Xu, M. Kalinowski, S. Majidy, C. Kokail, N. Maskara, E. C. Trapp, L. M. Stewart, S. Hollerith, H. Zhou, M. J. 

Gullans, S. F. Yelin, M. Greiner, V. Vuleti´c, M. Cain, and M. D. Lukin, A fault-tolerant neutral-atom architecture for universal quantum computation, Nature **649** , 39 (2026). 

- [42] Y. Li, Y. Bao, M. Peper, C. Li, and J. D. Thompson, Fast, continuous and coherent atom replacement in a neutral atom qubit array (2025), arXiv:2506.15633. 

- [43] M. Norcia, W. Cairncross, K. Barnes, P. Battaglino, A. Brown, M. Brown, K. Cassella, C.-A. Chen, R. Coxe, D. Crow, _et al._ , Midcircuit qubit measurement and rearrangement in a<sup>171</sup> Yb atomic array, Physical Review X **13** , 041034 (2023). 

- [44] M. N. Chow, V. Buchemmavari, S. Omanakuttan, B. J. Little, S. Pandey, I. H. Deutsch, and Y.-Y. Jau, Circuitbased leakage-to-erasure conversion in a neutral-atom quantum processor, PRX Quantum **5** , 040343 (2024). 

- [45] M. A. Rol, L. Ciorciaro, F. K. Malinowski, B. M. Tarasinski, R. E. Sagastizabal, C. C. Bultink, Y. Salathe, N. Haandbaek, J. Sedivy, and L. DiCarlo, Time-domain characterization and correction of on-chip distortion of control pulses in a quantum processor, Applied Physics Letters **116** , 054001 (2020). 

- [46] C. Hellings, N. Lacroix, A. Remm, R. Boell, J. Herrmann, S. Laz˘ar, S. Krinner, F. Swiadek, C. K. Andersen, C. Eichler, and A. Wallraff, Calibrating Magnetic Flux Control in Superconducting Circuits by Compensating Distortions on Time Scales from Nanoseconds up to Tens of Microseconds, Physical Review Research **7** , 10.1103/1qhb-r4fb (2025), arXiv:2503.04610. 

- [47] S. J. Evered, M. Xu, S. H. Li, A. A. Geim, J. Ataides, M. Kalinowski, D. Bluvstein, N. Maskara, C. Kokail, M. Greiner, _et al._ , High-fidelity entangling gates and nonlocal circuits with neutral atoms, arXiv:2604.25987 (2026). 

- [48] S. Saskin, J. T. Wilson, B. Grinkemeyer, and J. D. Thompson, Narrow-line cooling and imaging of ytterbium atoms in an optical tweezer array, Physical Review Letters **122** , 143002 (2019). 

- [49] J. Wilson, S. Saskin, Y. Meng, S. Ma, R. Dilip, A. Burgers, and J. Thompson, Trapping Alkaline Earth Rydberg Atoms Optical Tweezer Arrays, Physical Review Letters **128** , 033201 (2022).

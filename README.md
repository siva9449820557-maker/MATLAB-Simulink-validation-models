1. Model Objective
The model bridges the gap between analytical machine learning shortcuts and empirical cyber-physical networking reality. It acts as a high-fidelity, hardware-independent testbed to verify that the routing configurations optimized by the Artificial Neural Network (ANN) can handle physical path constraints while strictly maintaining the ≥ 90% safety availability threshold required for IEC 61508 SIL-1 compliance.
2. Physical Layout & Traffic Layer
The circuit isolates a multi-hop communications pipeline representing a critical 10-node routing path in a hostile industrial environment.
	Packet Stream: Driven by a sample-based Pulse Generator configured with a discrete sample clock interval of t_s=0.01\mathrm{\ s} (10 ms). The block outputs an integer pulse stream of values alternating between 0 and 1.
	Network Utilization: Operating at a baseline transmission rate of 165 Kbps with a fixed 900-bit packet payload size, the maximum theoretical line limit is 165,000 / 900 = 183.33 packets/sec. Injecting 100 packets/sec via the generator locks the circuit into a steady-state load utilization of 55.4%, mirroring a stable industrial safety network deployment.
	Memory Buffering: Packets exit the source node and pass into a First-In, First-Out (FIFO) Queue block from the DSP System Toolbox to monitor buffer memory behavior and avoid structural choke points during network jitter.
3. Energy-Aware Latency Loop \left(Z^{-d}\right)
Rather than evaluating network delays as a fixed, rigid constant, this architecture links remaining node battery reserves directly to processing bottlenecks.
	The Controller: A Nominal Average Residual Power (ResW = 0.75) block feeds into a subtraction loop (1-ResW=0.25powerloss). This loss multiplier passes through a Gain block (Value = 4) to output exactly 1 extra sample error offset (0.25 × 4 = 1).
	The Accumulator: This variable offset is added to a baseline constant of 5 samples, producing a total instruction delay length of 6 samples.
	The Variable Delay Block \left(Z^{-d}\right): The data stream enters port u, and the dynamic sample length enters control port d. Operating at a sample rate of 0.01s, a 6-sample delay yields a multi-hop transmission latency profile of exactly 0.060 seconds (60 ms). A Rate Transition block immediately follows to isolate data streams and prevent down-stream processing collisions.
4. Stochastic Threat Injection & Routing Gates
Environmental path loss (-83 dB) and industrial background radio frequency white noise are simulated simultaneously using standard math blocks.
	The Nominal ResW (0.75) line branches into a Product block alongside a Uniform Random Number Generator bounding outputs between 0 and 1.
	The output streams into a Relational Operator set to a loose, calibrated compliance ceiling (<= 0.09, representing a relaxed 9% fault margin).
	The output maps onto a Multiport Switch using Zero-based contiguous indexing:
	Control Vector reads 0: Opens Port 0, routing surviving data pulses smoothly to the success data sink.
	Control Vector reads 1: Opens Port 1, routing a static high-alarm constant block (Value = 1) to the data track to log a True Positive Successful Detection (SDR) event.
	Default Context: Any out-of-bound variance drops signals to a static constant baseline zero block (Value = 0) linked to the remaining sinks, representing structural packet erasure or False Positive Alerts (FPDR).
5. Data Sinks & Workspace Evaluation Mapping
To maintain version compatibility across old and new MATLAB engines, four distinct data sinks (success, dropout, alertTrue, alertFalse) are connected across separate monitoring coordinates to pipe raw data elements directly back into the MATLAB workspace arrays:
	dropout: Connected right after the Queue to register total packet attempts.
	success: Connected to the final switch output to capture successful base station arrivals.
	alertTrue: Branching off the relational operator line to catch threat detection events.
	alertFalse: Tied to the standalone constant 0 block to create a controlled error baseline register.

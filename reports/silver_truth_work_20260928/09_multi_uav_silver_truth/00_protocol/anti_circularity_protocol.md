# Anti-circularity protocol

For UAV i, generate P(-i) from other UAVs only. Evaluate i with its independent manual source pixel or compare P(-i) with accepted LRF. Its camera pose and intrinsics may be used only to project P(-i), never its marked source pixel to construct P(-i). B3 manual north/south topology is an input identity assumption; its held-out match score is conditional on that assumption. Do not use association ray residual itself to establish identity truth, and do not reuse frames as independent events. Background-only visual camera fitting does not use source LRF.

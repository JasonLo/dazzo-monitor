import numpy as np


class ActivityClassifier:
    """Lightweight activity classifier using accelerometer-only data.

    Due to power budget in the transmitter, we avoid full IMU fusion and
    estimate motion from acceleration alone. Thresholds are expressed in
    multiples of g ("g units").
    """

    def __init__(
        self,
        rest_threshold: float = 0.2,
        active_threshold: float = 1.0,
        g: float = 9.73,
    ) -> None:
        # Thresholds are in "g" units (multiples of acceleration due to gravity)
        self.rest_threshold = rest_threshold
        self.active_threshold = active_threshold
        self.g = g

    def classify(self, data: np.ndarray, input_type: str = "accelerometer") -> str:
        """Classify activity level based on a window of acceleration samples.

        Parameters:
            data: Array-like of shape (N, 3) with acceleration samples (x, y, z)
                  in m/s^2. If a single 3-vector is provided, it will be treated
                  as a window of length 1.
            input_type: "accelerometer" if values include gravity; "linear" if
                        gravity has already been removed (e.g., sensor's linear
                        acceleration output).

        Returns:
            str: one of 'resting', 'active', or 'highly active' with the
                 mean dynamic acceleration reported in g units.

        Notes:
            - Simply using ||a|| - g is not a valid gravity removal in general
              (it underestimates lateral motion by ~A^2/(2g)). Instead, we
              estimate and subtract the mean acceleration vector over the
              window to approximate the gravity/bias vector, then take the
              magnitude of the residual.
        """

        arr = np.asarray(data, dtype=float)
        if arr.ndim == 1:
            if arr.size != 3:
                raise ValueError("Expected a 3-vector or an (N,3) array of samples")
            arr = arr[None, :]  # (1, 3)
        if arr.shape[1] != 3:
            raise ValueError("Input must have shape (N, 3)")

        if input_type.lower() in {"accelerometer", "accel", "raw"}:
            # Approximate gravity as the mean acceleration vector in the window (bad but power efficient)
            g_vec = arr.mean(axis=0)
            dynamic = arr - g_vec
        else:
            # Assume gravity already removed (sensor-provided linear acceleration)
            dynamic = arr

        # Mean magnitude of dynamic acceleration (m/s^2)
        scalar = np.linalg.norm(dynamic, axis=1)
        mean_acc_ms2 = float(np.mean(scalar))

        # Convert to g units for threshold and reporting
        mean_acc_g = mean_acc_ms2 / self.g

        if mean_acc_g < self.rest_threshold:
            return f"resting ({mean_acc_g:.2f}g)"
        elif mean_acc_g < self.active_threshold:
            return f"active ({mean_acc_g:.2f}g)"
        else:
            return f"highly active ({mean_acc_g:.2f}g)"

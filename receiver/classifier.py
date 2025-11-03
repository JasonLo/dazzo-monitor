from enum import StrEnum

import numpy as np


class SensorMode(StrEnum):
    ACCONLY = "accelerometer only"
    NDOF = "Nine degree of freedom Kalman filter"


class LinearAccelerationKF:
    """
    Estimate gravity and linear acceleration from accelerometer-only data
    using a 6-state Kalman filter.

    State: [g_bx, g_by, g_bz, a_lx, a_ly, a_lz]
    - g_b: gravity vector in body frame (constant over short windows)
    - a_l: linear acceleration (AR(1) process with decay phi)
    """

    def __init__(
        self,
        fs: float = 30.0,
        tau_target: float = 0.1,
        r: float = 0.05,
        qg_base: float = 1e-3,
        qa_base: float = 0.02,
    ) -> None:
        """
        Initialize Kalman filter with auto-tuned parameters.

        Parameters:
            fs: Sampling frequency in Hz
            tau_target: Target time constant for acceleration decay (seconds)
            r: Measurement noise variance (m/s²)²
            qg_base: Base gravity process noise at 100 Hz reference
            qa_base: Base acceleration process noise
        """
        self.fs = float(fs)
        self.dt = 1.0 / self.fs

        # Calculate optimal parameters for given sampling rate
        self.phi = float(np.exp(-self.dt / tau_target))
        qg = qg_base * (100.0 / fs)
        qa = qa_base

        # State transition matrix
        self.F = np.block(
            [
                [np.eye(3), np.zeros((3, 3))],  # gravity stays constant
                [np.zeros((3, 3)), self.phi * np.eye(3)],  # acceleration decays
            ]
        )

        # Measurement matrix: z = g + a_lin
        self.H = np.hstack([np.eye(3), np.eye(3)])

        # Process noise covariance (discrete-time)
        qg_d = qg * self.dt  # gravity random walk
        qa_d = qa * (1.0 - self.phi**2)  # AR(1) steady-state variance
        self.Q = np.diag([qg_d, qg_d, qg_d, qa_d, qa_d, qa_d])

        # Measurement noise covariance
        self.R = np.eye(3) * r

        # State and covariance
        self.x = np.zeros(6)
        self.P = np.eye(6)

        # Pre-compute constants for efficiency
        self._I6 = np.eye(6)
        self._FT = self.F.T
        self._HT = self.H.T

    def initialize_gravity(self, accel_samples: np.ndarray) -> None:
        """
        Initialize gravity estimate from stationary acceleration samples.

        Parameters:
            accel_samples: (N, 3) array of acceleration measurements
        """
        g0 = np.mean(accel_samples, axis=0)
        self.x[:3] = g0
        self.x[3:] = 0.0  # linear acceleration starts at zero
        # Lower initial uncertainty after initialization
        self.P = np.diag([0.1, 0.1, 0.1, 1.0, 1.0, 1.0])

    def update(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Perform one Kalman filter update step.

        Parameters:
            z: 3-element acceleration measurement (m/s²)

        Returns:
            (g_est, a_lin_est): Estimated gravity and linear acceleration vectors
        """
        # Predict
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self._FT + self.Q

        # Update
        y = z - self.H @ x_pred  # innovation
        S = self.H @ P_pred @ self._HT + self.R  # innovation covariance
        # Kalman gain (numerically stable using solve)
        K = (P_pred @ self._HT @ np.linalg.inv(S)).astype(np.float64)

        self.x = x_pred + K @ y
        # Joseph form covariance update (ensures positive-definiteness)
        IKH = self._I6 - K @ self.H
        self.P = IKH @ P_pred @ IKH.T + K @ self.R @ K.T

        return self.x[:3].copy(), self.x[3:].copy()

    def get_state(self) -> dict[str, np.ndarray]:
        """Return current filter state."""
        return {
            "gravity": self.x[:3].copy(),
            "linear_accel": self.x[3:].copy(),
            "covariance": self.P.copy(),
        }

    def reset(self) -> None:
        """Reset filter to initial state."""
        self.x = np.zeros(6)
        self.P = np.eye(6)


class ActivityClassifier:
    """Lightweight activity classifier using sensor data."""

    def __init__(
        self,
        sensor_mode: SensorMode = SensorMode.ACCONLY,
        rest_threshold: float = 1.0,
        active_threshold: float = 3.0,
        fs: float = 30.0,
    ) -> None:
        self.sensor_mode = sensor_mode
        self.rest_threshold = rest_threshold
        self.active_threshold = active_threshold
        # Sampling rate for the accelerometer stream (Hz)
        self.fs: float = float(fs)
        # Lazily created Kalman filter for accelerometer-only mode
        self._kf: LinearAccelerationKF | None = None

    def classify(self, data: np.ndarray) -> dict[str, str | float]:
        """Classify activity level based on a window of acceleration samples.

        Parameters:
            data: Array-like of shape (N, 3) with acceleration samples (x, y, z)
                  in m/s^2. If a single 3-vector is provided, it will be treated
                  as a window of length 1.

        Returns:
            dict[str, str | float]: Classification result containing one of 'resting', 'active', or 'highly active'
                                      with the mean dynamic acceleration reported in ms-2 units.

        """

        arr = np.asarray(data, dtype=float)
        if arr.ndim == 1:
            if arr.size != 3:
                raise ValueError("Expected a 3-vector or an (N,3) array of samples")
            arr = arr[None, :]  # (1, 3)
        if arr.shape[1] != 3:
            raise ValueError("Input must have shape (N, 3)")

        if self.sensor_mode == SensorMode.ACCONLY:
            # Use a lightweight 6-state Kalman filter to separate gravity and linear acceleration.
            if self._kf is None:
                self._kf = LinearAccelerationKF(fs=self.fs)
                # Initialize gravity estimate using the first window (assumed roughly stationary on average)
                self._kf.initialize_gravity(arr)

            dyn_list: list[np.ndarray] = []
            for z in arr:
                _, a_lin = self._kf.update(z)
                dyn_list.append(a_lin)
            dynamic = np.vstack(dyn_list)
        elif self.sensor_mode == SensorMode.NDOF:
            dynamic = arr
        else:
            raise ValueError(f"Unsupported sensor mode: {self.sensor_mode}")

        # Mean magnitude of dynamic acceleration (m/s^2)
        mean_acc = float(np.mean(np.linalg.norm(dynamic, axis=1)))

        if mean_acc < self.rest_threshold:
            return {"activity": "resting", "mean_acc": mean_acc}
        elif mean_acc < self.active_threshold:
            return {"activity": "active", "mean_acc": mean_acc}
        else:
            return {"activity": "highly active", "mean_acc": mean_acc}

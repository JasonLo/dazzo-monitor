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
    """

    # --- Class attributes ---
    fs: float
    dt: float
    phi: float
    F: np.ndarray  # 6x6 state transition matrix
    H: np.ndarray  # 3x6 measurement matrix
    Q: np.ndarray  # 6x6 process noise covariance
    R: np.ndarray  # 3x3 measurement noise covariance
    x: np.ndarray  # 6-element state vector
    P: np.ndarray  # 6x6 state covariance matrix

    def __init__(
        self,
        fs: float = 100.0,
        phi: float = 0.98,
        qg: float = 1e-3,
        qa: float = 1e-1,
        r: float = 0.05,
    ) -> None:
        self.fs = float(fs)
        self.dt = 1.0 / self.fs
        self.phi = float(phi)

        self.F = np.block(
            [
                [np.eye(3), np.zeros((3, 3))],
                [np.zeros((3, 3)), self.phi * np.eye(3)],
            ]
        )
        self.H = np.hstack([np.eye(3), np.eye(3)])

        # Discrete-time process noise: gravity random walk scales with dt,
        # AR(1) acceleration uses (1 - phi^2) scaling.
        qg_d: float = qg * self.dt
        qa_d: float = qa * (1.0 - self.phi**2)
        self.Q = np.diag([qg_d] * 3 + [qa_d] * 3)

        self.R = np.eye(3) * r
        self.x = np.zeros(6)
        self.P = np.eye(6) * 1.0

    def initialize_gravity(self, accel_samples: np.ndarray) -> None:
        """Use average of stationary samples for initial gravity estimate."""
        g0: np.ndarray = np.mean(accel_samples, axis=0)
        self.x[:3] = g0
        self.P = np.eye(6) * 0.1

    def update(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Perform one KF step given accel measurement z (3-vector)."""
        # predict
        x_pred: np.ndarray = self.F @ self.x
        P_pred: np.ndarray = self.F @ self.P @ self.F.T + self.Q

        # measurement update
        y: np.ndarray = z - self.H @ x_pred
        S: np.ndarray = self.H @ P_pred @ self.H.T + self.R
        K: np.ndarray = P_pred @ self.H.T @ np.linalg.inv(S)
        self.x = x_pred + K @ y
        self.P = (np.eye(6) - K @ self.H) @ P_pred

        g_est: np.ndarray = self.x[:3]
        a_lin_est: np.ndarray = self.x[3:]
        return g_est, a_lin_est


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

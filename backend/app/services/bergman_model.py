"""
GlucoTwin AI - Bergman Minimal Model ODE Simulation Engine
Implements physiological Type 1 Diabetes glucose-insulin dynamics based on the classical Minimal Model
(Bergman et al., 1979 / 1981) with exogenous prandial carbohydrate absorption and subcutaneous insulin kinetics.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class BergmanMinimalModel:
    """
    Physiological Bergman Minimal Model ordinary differential equation (ODE) simulator.

    Equations:
    dG/dt = -(p1 + X + E(t)) * G + p1 * Gb + Ra(t) / VI
    dX/dt = -p2 * X + p3 * (I - Ib)
    dI/dt = -n * (I - Ib) + U(t) / VI
    """

    def __init__(
        self,
        body_weight_kg: float = 70.0,
        basal_glucose: float = 110.0,
        basal_insulin: float = 12.0,
        p1: float = 0.028,      # Glucose effectiveness (min^-1)
        p2: float = 0.025,      # Rate of insulin action clearance (min^-1)
        p3: float = 0.000018,   # Insulin sensitivity parameter (min^-2 / (uU/mL))
        n: float = 0.22,        # Insulin fractional clearance (min^-1)
        tau_meal: float = 40.0, # Mean gut transit time (minutes)
        tau_insulin: float = 55.0 # Mean insulin absorption time (minutes)
    ):
        self.body_weight_kg = body_weight_kg
        self.Gb = basal_glucose
        self.Ib = basal_insulin
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.n = n
        self.tau_meal = tau_meal
        self.tau_insulin = tau_insulin

        # Glucose distribution volume in dL (approx 1.4 dL/kg * weight)
        self.VI_glucose = 1.4 * self.body_weight_kg
        # Plasma insulin distribution volume in mL (approx 140.0 mL/kg * weight)
        self.VI_insulin = 140.0 * self.body_weight_kg

    def _rate_of_glucose_appearance(
        self,
        t: float,
        meals: List[Tuple[float, float]] # list of (t_meal, carbs_grams)
    ) -> float:
        """Computes rate of appearance of glucose Ra(t) in mg/min."""
        ra_total = 0.0
        bioavailability = 0.85  # 85% absorbed as glucose

        for t_meal, carbs in meals:
            if t >= t_meal:
                dt = t - t_meal
                # Total mg of glucose from meal
                total_mg = carbs * 1000.0 * bioavailability
                # Two-compartment absorption impulse response: (dt / tau^2) * exp(-dt / tau)
                ra = total_mg * (dt / (self.tau_meal ** 2)) * np.exp(-dt / self.tau_meal)
                ra_total += ra
        return ra_total

    def _rate_of_insulin_appearance(
        self,
        t: float,
        boluses: List[Tuple[float, float]] # list of (t_bolus, bolus_units)
    ) -> float:
        """Computes rate of appearance of synthetic insulin U(t) in uU/min."""
        u_total = 0.0
        # 1 Unit of insulin = 1e6 microUnits (uU)

        for t_bolus, units in boluses:
            if t >= t_bolus:
                dt = t - t_bolus
                total_uu = units * 1e6
                u = total_uu * (dt / (self.tau_insulin ** 2)) * np.exp(-dt / self.tau_insulin)
                u_total += u
        return u_total

    def _exercise_uptake_factor(
        self,
        t: float,
        exercises: List[Tuple[float, float, int]] # list of (t_start, duration_min, intensity)
    ) -> float:
        """Computes acute exercise insulin-independent glucose clearance factor E(t)."""
        e_total = 0.0
        for t_start, duration, intensity in exercises:
            if t >= t_start:
                dt = t - t_start
                if dt <= duration:
                    # Active exercise phase: clearance scales with intensity (1 to 3)
                    e_total += 0.005 * intensity
                elif dt <= duration + 60.0:
                    # Post-exercise recovery window: decaying enhanced uptake
                    decay_dt = dt - duration
                    e_total += (0.005 * intensity) * np.exp(-decay_dt / 30.0)
        return e_total

    def derivatives(
        self,
        t: float,
        state: np.ndarray,
        meals: List[Tuple[float, float]],
        boluses: List[Tuple[float, float]],
        exercises: List[Tuple[float, float, int]]
    ) -> np.ndarray:
        """
        Computes state derivatives [dG/dt, dX/dt, dI/dt].
        """
        G, X, I = state

        Ra = self._rate_of_glucose_appearance(t, meals)
        U = self._rate_of_insulin_appearance(t, boluses)
        E = self._exercise_uptake_factor(t, exercises)

        # dG/dt: glucose rate of change
        dG = -(self.p1 + X + E) * G + self.p1 * self.Gb + (Ra / self.VI_glucose)

        # dX/dt: remote insulin action
        dX = -self.p2 * X + self.p3 * (I - self.Ib)

        # dI/dt: plasma insulin dynamics
        dI = -self.n * (I - self.Ib) + (U / self.VI_insulin)

        return np.array([dG, dX, dI])

    def simulate(
        self,
        duration_minutes: float = 240.0,
        step_minutes: float = 5.0,
        initial_glucose: Optional[float] = None,
        initial_insulin_action: float = 0.0,
        initial_plasma_insulin: Optional[float] = None,
        meals: Optional[List[Tuple[float, float]]] = None,
        boluses: Optional[List[Tuple[float, float]]] = None,
        exercises: Optional[List[Tuple[float, float, int]]] = None
    ) -> Dict[str, np.ndarray]:
        """
        Simulates the Bergman ODE forward in time using 4th-order Runge-Kutta (RK4) integration.
        Returns time points, glucose trajectory, remote insulin action, and plasma insulin.
        """
        meals = meals or []
        boluses = boluses or []
        exercises = exercises or []

        g0 = initial_glucose if initial_glucose is not None else self.Gb
        i0 = initial_plasma_insulin if initial_plasma_insulin is not None else self.Ib
        state = np.array([g0, initial_insulin_action, i0], dtype=np.float64)

        num_steps = int(duration_minutes / step_minutes) + 1
        times = np.linspace(0.0, duration_minutes, num_steps)

        glucose_traj = np.zeros(num_steps)
        action_traj = np.zeros(num_steps)
        insulin_traj = np.zeros(num_steps)

        # Sub-step RK4 for numerical precision (dt_sub = 0.5 minutes)
        sub_steps = 10
        dt_sub = step_minutes / sub_steps

        for i, t in enumerate(times):
            # Clamp states to physiological feasibility
            state[0] = np.clip(state[0], 40.0, 500.0)
            state[1] = max(0.0, state[1])
            state[2] = max(0.0, state[2])

            glucose_traj[i] = round(float(state[0]), 1)
            action_traj[i] = float(state[1])
            insulin_traj[i] = float(state[2])

            if i < num_steps - 1:
                current_t = t
                for _ in range(sub_steps):
                    k1 = self.derivatives(current_t, state, meals, boluses, exercises)
                    k2 = self.derivatives(current_t + 0.5 * dt_sub, state + 0.5 * dt_sub * k1, meals, boluses, exercises)
                    k3 = self.derivatives(current_t + 0.5 * dt_sub, state + 0.5 * dt_sub * k2, meals, boluses, exercises)
                    k4 = self.derivatives(current_t + dt_sub, state + dt_sub * k3, meals, boluses, exercises)

                    state += (dt_sub / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
                    current_t += dt_sub

        return {
            "times": times,
            "glucose": glucose_traj,
            "insulin_action": action_traj,
            "plasma_insulin": insulin_traj
        }

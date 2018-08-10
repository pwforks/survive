"""Implements the Nelson-Aalen cumulative hazard estimator."""

import numpy as np
import scipy.stats as st

from .base import NonparametricEstimator
from .. import SurvivalData


class NelsonAalen(NonparametricEstimator):
    """Nelson-Aalen cumulative hazard estimator.

    Parameters
    ----------
    conf_type : {'linear'}
        Type of confidence interval for the cumulative hazard estimate to
        report.

    conf_level : float
        Confidence level of the confidence intervals.

    tie_break : {'discrete', 'continuous'}
        Specify how to handle tied event times.
    """
    model_type = "Nelson-Aalen estimator"
    _estimand = "cumulative hazard"
    _estimate0 = 0.

    _conf_types = ("linear",)

    # How to handle tied event times for the Aalen-Johansen variance estimator
    _tie_breaks = ("continuous", "discrete")
    _tie_break: str

    @property
    def tie_break(self):
        """How to handle tied event times."""
        return self._tie_break

    @tie_break.setter
    def tie_break(self, tie_break):
        """Set the tie-breaking scheme."""
        if tie_break in self._tie_breaks:
            self._tie_break = tie_break
        else:
            raise ValueError(f"Invalid value for 'tie_break': {tie_break}.")

    def __init__(self, conf_type="linear", conf_level=0.95,
                 tie_break="discrete"):
        self.conf_type = conf_type
        self.conf_level = conf_level
        self.tie_break = tie_break

    def fit(self, time, **kwargs):
        """Fit the Nelson-Aalen estimator to survival data.

        Parameters
        ----------
        time : one-dimensional array-like or str or SurvivalData
            The observed times, or all the survival data. If this is a
            :class:`survive.SurvivalData` instance, then it is used to fit the
            estimator and any other parameters are ignored. Otherwise, `time`
            and the keyword arguments in `kwargs` are used to initialize a
            :class:`survive.SurvivalData` object on which this estimator is
            fitted.

        **kwargs : keyword arguments
            Any additional keyword arguments used to initialize a
            :class:`survive.SurvivalData` instance.

        Returns
        -------
        survive.nonparametric.NelsonAalen
            This estimator.

        See Also
        --------
        survive.SurvivalData : Structure used to store survival data.
        """
        if isinstance(time, SurvivalData):
            self._data = time
        else:
            self._data = SurvivalData(time, **kwargs)

        # Compute the Nelson-Aalen estimator and related quantities at the
        # distinct failure times within each group
        self.estimate_ = []
        self.estimate_var_ = []
        self.estimate_ci_lower_ = []
        self.estimate_ci_upper_ = []
        for i, group in enumerate(self._data.group_labels):
            # d = number of events at an event time, y = size of the risk set at
            # an event time
            d = self._data.events[group].n_events
            y = self._data.events[group].n_at_risk

            # Compute the cumulative hazard and variance estimates
            if self._tie_break == "discrete":
                self.estimate_.append(np.cumsum(d / y))
                self.estimate_var_.append(np.cumsum((y - d) * d / (y ** 3)))
            elif self._tie_break == "continuous":
                na_increments = np.empty(len(d), dtype=np.float_)
                var_increments = np.empty(len(d), dtype=np.float_)
                for j in range(len(d)):
                    temp = y[j] - np.arange(d[j])
                    na_increments[j] = np.sum(1 / temp)
                    var_increments[j] = np.sum(1 / temp ** 2)
                self.estimate_.append(np.cumsum(na_increments))
                self.estimate_var_.append(np.cumsum(var_increments))
            else:
                # This should not be reachable
                raise RuntimeError(
                    f"Invalid tie-breaking scheme: {self._tie_break}.")

            # Standard normal quantile for confidence intervals
            z = st.norm.ppf((1 - self.conf_level) / 2)

            # Compute confidence intervals at the observed event times
            if self._conf_type == "linear":
                # Normal approximation CI
                c = z * np.sqrt(self.estimate_var_[i])
                lower = self.estimate_[i] + c
                upper = self.estimate_[i] - c
            else:
                # This should not be reachable
                raise RuntimeError(
                    f"Invalid confidence interval type: {self._conf_type}.")

            # Force confidence interval lower bound to be 0
            with np.errstate(invalid="ignore"):
                self.estimate_ci_lower_.append(np.maximum(lower, 0.))
                self.estimate_ci_upper_.append(upper)

            # Make sure that variance estimates and confidence intervals are NaN
            # when the estimated survival probability is zero
            ind_zero = (self.estimate_[i] == 0.)
            self.estimate_var_[i][ind_zero] = np.nan
            self.estimate_ci_lower_[i][ind_zero] = np.nan
            self.estimate_ci_upper_[i][ind_zero] = np.nan

        self.fitted = True
        return self

"""
Este algoritmo fue realizado para la clase de Algoritmos de la Universidad Nacional de Colombia, basado en el ejemplo Cross-sectional Equity Template Example 

Estudiante: Liseth Yurany Arévalo Yaruro
"""

import quantopian.algorithm as algo
import quantopian.optimize as opt
from quantopian.pipeline import Pipeline
from quantopian.pipeline.factors import SimpleMovingAverage

from quantopian.pipeline.filters import QTradableStocksUS
from quantopian.pipeline.experimental import risk_loading_pipeline

from quantopian.pipeline.data.psychsignal import stocktwits
from quantopian.pipeline.data import Fundamentals

# Constraint Parameters
MAX_GROSS_LEVERAGE = 1.0
TOTAL_POSITIONS = 600

MAX_SHORT_POSITION_SIZE = 2.0 / TOTAL_POSITIONS
MAX_LONG_POSITION_SIZE = 2.0 / TOTAL_POSITIONS


def initialize(context):
    
    algo.attach_pipeline(make_pipeline(), 'long_short_equity_template')
    algo.attach_pipeline(risk_loading_pipeline(), 'risk_factors')

    algo.schedule_function(func=rebalance,
                           date_rule=algo.date_rules.week_start(),
                           time_rule=algo.time_rules.market_open(hours=0, minutes=30),
                           half_days=True)

    algo.schedule_function(func=record_vars,
                           date_rule=algo.date_rules.every_day(),
                           time_rule=algo.time_rules.market_close(),
                           half_days=True)


def make_pipeline():
    value = Fundamentals.ebitda.latest / Fundamentals.enterprise_value.latest
    favor = Fundamentals.accounts_receivable.latest
    porrec = Fundamentals.total_capitalization.latest
    bank = Fundamentals.revenue_growth.latest
    sale = Fundamentals.sale_of_investment.latest
    quality = Fundamentals.roe.latest

    universe = QTradableStocksUS()
    
    value_winsorized = value.winsorize(min_percentile=0.05, max_percentile=0.95)
    favor_winsorized = favor.winsorize(min_percentile=0.05, max_percentile=0.95)
    porrec_winsorized = porrec.winsorize(min_percentile=0.05, max_percentile=0.95)
    bank_winsorized = bank.winsorize(min_percentile=0.05, max_percentile=0.95)
    sale_winsorized = sale.winsorize(min_percentile=0.05, max_percentile=0.95)
    quality_winsorized = quality.winsorize(min_percentile=0.05, max_percentile=0.95)

    combined_factor = (
        value_winsorized.zscore()*0.2+ 
        quality_winsorized.zscore()*0.3+ 
        favor_winsorized.zscore()*0.2 + 
        porrec_winsorized.zscore()*0.05 +
        sale_winsorized.zscore()*0.1+
        bank_winsorized.zscore()*0.05 
    )

    longs = combined_factor.top(TOTAL_POSITIONS//2, mask=universe)
    shorts = combined_factor.bottom(TOTAL_POSITIONS//2, mask=universe)

    long_short_screen = (longs | shorts)

    # Create pipeline
    pipe = Pipeline(
        columns={
            'longs': longs,
            'shorts': shorts,
            'combined_factor': combined_factor
        },
        screen=long_short_screen
    )
    return pipe


def before_trading_start(context, data):

    context.pipeline_data = algo.pipeline_output('long_short_equity_template')

    context.risk_loadings = algo.pipeline_output('risk_factors')


def record_vars(context, data):

    algo.record(num_positions=len(context.portfolio.positions))

def rebalance(context, data):

    pipeline_data = context.pipeline_data

    risk_loadings = context.risk_loadings

    objective = opt.MaximizeAlpha(pipeline_data.combined_factor)

    # Define the list of constraints
    constraints = []
    # Constrain our maximum gross leverage
    constraints.append(opt.MaxGrossExposure(MAX_GROSS_LEVERAGE))

    # Require our algorithm to remain dollar neutral
    constraints.append(opt.DollarNeutral())

    # Add the RiskModelExposure constraint to make use of the
    # default risk model constraints
    neutralize_risk_factors = opt.experimental.RiskModelExposure(
        risk_model_loadings=risk_loadings,
        version=0
    )
    constraints.append(neutralize_risk_factors)

    # With this constraint we enforce that no position can make up
    # greater than MAX_SHORT_POSITION_SIZE on the short side and
    # no greater than MAX_LONG_POSITION_SIZE on the long side. This
    # ensures that we do not overly concentrate our portfolio in
    # one security or a small subset of securities.
    constraints.append(
        opt.PositionConcentration.with_equal_bounds(
            min=-MAX_SHORT_POSITION_SIZE,
            max=MAX_LONG_POSITION_SIZE
        ))

    # Put together all the pieces we defined above by passing
    # them into the algo.order_optimal_portfolio function. This handles
    # all of our ordering logic, assigning appropriate weights
    # to the securities in our universe to maximize our alpha with
    # respect to the given constraints.
    algo.order_optimal_portfolio(
        objective=objective,
        constraints=constraints
    )

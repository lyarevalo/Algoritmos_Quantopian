import quantopian.algorithm as algo
import quantopian.optimize as opt
from quantopian.pipeline import Pipeline
from quantopian.pipeline.factors import SimpleMovingAverage
from quantopian.pipeline.filters import QTradableStocksUS
from quantopian.pipeline.experimental import risk_loading_pipeline
from quantopian.pipeline.domain import US_EQUITIES
from  quantopian.pipeline.data  import  Fundamentals
from quantopian.pipeline.data import factset
from quantopian.pipeline.data import morningstar 

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
    
    v1 = factset.Fundamentals.com_eq_retain_earn.latest
    v3 = morningstar.Fundamentals.sale_of_investment.latest
    v2 = Fundamentals.market_cap.latest
    v4 = morningstar.Fundamentals.diluted_eps_growth.latest
    v5 = morningstar.Fundamentals.buy_back_yield.latest
    #v6 = Fundamentals.value_score.latest
    
    
    
   
    universe = QTradableStocksUS()
    
    #value_winsorized = value.winsorize(min_percentile=0.05, max_percentile=0.95)
    v1_winsorized = v1.winsorize(min_percentile=0.05, max_percentile=0.95)
    v2_winsorized = v2.winsorize(min_percentile=0.05, max_percentile=0.95)
    v3_winsorized = v3.winsorize(min_percentile=0.05, max_percentile=0.95)
    v4_winsorized = v4.winsorize(min_percentile=0.05, max_percentile=0.95)
    v5_winsorized = v5.winsorize(min_percentile=0.05, max_percentile=0.95)
    #v6_winsorized = v6.winsorize(min_percentile=0.05, max_percentile=0.95)
 


    combined_factor = (
        #value_winsorized.zscore() +
        v1_winsorized.zscore()*0.2+
        v2_winsorized.zscore()*0.01+ 
        v3_winsorized.zscore()*0.1+  
        (v4_winsorized.zscore()*0.1*  
        v5_winsorized.zscore()*0.1) 
        #v6_winsorized.zscore()*0.2

    )

    longs = combined_factor.top(TOTAL_POSITIONS//2, mask=universe)
    shorts = combined_factor.bottom(TOTAL_POSITIONS//2, mask=universe)

    long_short_screen = (longs | shorts)

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


# Called at the start of every month in order to rebalance
# the longs and shorts lists

#maximizar entabiidad
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


    constraints.append(
        opt.PositionConcentration.with_equal_bounds(
            min=-MAX_SHORT_POSITION_SIZE,
            max=MAX_LONG_POSITION_SIZE
        ))

    algo.order_optimal_portfolio(
        objective=objective,
        constraints=constraints
    )

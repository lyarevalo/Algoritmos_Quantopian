"""
Este algoritmo fue realizado para la clase de Algoritmos de la Universidad Nacional de Colombia, basado en el ejemplo Cross-sectional Equity Template Example 

Estudiante: Liseth Yurany Arévalo Yaruro
"""

import quantopian.algorithm as algo
import quantopian.optimize as opt
#recoger datos, procesarlos y convertirlos en variables de decision
from quantopian.pipeline import Pipeline
#prmedio movil, cada cuantas observaciones el promedio
from quantopian.pipeline.factors import SimpleMovingAverage
#stocks en lo s que se pueden invertir
from quantopian.pipeline.filters import QTradableStocksUS
#construir por tafolio de acuerdo al riesgo x sectores
from quantopian.pipeline.experimental import risk_loading_pipeline
#Analisis del feed de twitter
#obtener info de la compañia
from quantopian.pipeline.data.factset import Fundamentals

# Constraint Parameters
#apalancamiento
MAX_GROSS_LEVERAGE = 1.0
#numero total
TOTAL_POSITIONS = 600
#estará sujeto a volumenes de negociación?


# Here we define the maximum position size that can be held for any
# given stock. If you have a different idea of what these maximum
# sizes should be, feel free to change them. Keep in mind that the
# optimizer needs some leeway in order to operate. Namely, if your
# maximum is too small, the optimizer may be overly-constrained.

#maxima posicion es 2 sobre 600
MAX_SHORT_POSITION_SIZE = 2.0 / TOTAL_POSITIONS
MAX_LONG_POSITION_SIZE = 2.0 / TOTAL_POSITIONS


def initialize(context):
    """
    A core function called automatically once at the beginning of a backtest.

    Use this function for initializing state or other bookkeeping.

    Parameters
    ----------
    context : AlgorithmContext
        An object that can be used to store state that you want to maintain in 
        your algorithm. context is automatically passed to initialize, 
        before_trading_start, handle_data, and any functions run via schedule_function.
        context provides the portfolio attribute, which can be used to retrieve information 
        about current positions.
    """
    
    algo.attach_pipeline(make_pipeline(), 'long_short_equity_template')

    # Attach the pipeline for the risk model factors that we
    # want to neutralize in the optimization step. The 'risk_factors' string is 
    # used to retrieve the output of the pipeline in before_trading_start below.
    algo.attach_pipeline(risk_loading_pipeline(), 'risk_factors')

    # Schedule our rebalance function
    algo.schedule_function(func=rebalance,
                           date_rule=algo.date_rules.week_start(),
                           time_rule=algo.time_rules.market_open(hours=0, minutes=30),
                           half_days=True)

    # Record our portfolio variables at the end of day
    algo.schedule_function(func=record_vars,
                           date_rule=algo.date_rules.every_day(),
                           time_rule=algo.time_rules.market_close(),
                           half_days=True)


def make_pipeline():
    """
    A function that creates and returns our pipeline.

    We break this piece of logic out into its own function to make it easier to
    test and modify in isolation. In particular, this function can be
    copy/pasted into research and run by itself.

    Returns
    -------
    pipe : Pipeline
        Represents computation we would like to perform on the assets that make
        it through the pipeline screen.
        ##recoge info rde las 8 mil compañias
    """
    # The factors we create here are based on fundamentals data and a moving
    # average of sentiment data
    
    ##colocar mas variables
    #utliizar precios volumenes, retornos
    #ampliar aminimo 10 variables
    #buscarlas en quantipian
    #darle ventaja al algoritmo
    #podemos poner factores de peso o multiplicadores si la variable es importante
    #pesos de ponderacion 
    #factor combiando es el que elije las mejore 300 y las peores 300
    #average y riesgo por sectores
    #por qué contribuye la variable, a decir si ayuda a predecir si baja o no
    #correrlo 6 meses y 2 años
    
    
    enterprise = Fundamentals.com_eq_retain_earn.latest
    enterprise2 = Fundamentals.invest_inc_af.latest
    volume = Fundamentals.volume_trade_af.latest
    capital = Fundamentals.invest_cap_af.latest
    inb = Fundamentals.sales_af.latest
    num = Fundamentals.entrpr_val_af.latest
   
   
    universe = QTradableStocksUS()
    
    # We winsorize our factor values in order to lessen the impact of outliers
    # For more information on winsorization, please see
    # https://en.wikipedia.org/wiki/Winsorizing
    
    #Toma todas las ccione sde quantopian y crea una tabla con 3 cristerior, valro,         calidad  
    #dataframe pandas, como hoja de excel
    
    enterprise_winsorized = enterprise.winsorize(min_percentile=0.05, max_percentile=0.95)
    enterprise2_winsorized = enterprise2.winsorize(min_percentile=0.05, max_percentile=0.95)
    volume_winsorized = volume.winsorize(min_percentile=0.05, max_percentile=0.95)
    capital_winsorized = capital.winsorize(min_percentile=0.05, max_percentile=0.95)
    inb_winsorized = inb.winsorize(min_percentile=0.05, max_percentile=0.95)
    num_winsorized = num.winsorize(min_percentile=0.05, max_percentile=0.95)
   

    # Here we combine our winsorized factors, z-scoring them to equalize their influence
    #combina los factoes, coge columna, la normaliza y la vuelve entre  0 y 1 y las suma
    
    combined_factor = (
        enterprise_winsorized.zscore()*0.27+
        enterprise2_winsorized.zscore()*0.2 +
        volume_winsorized.zscore()*0.1+
        capital_winsorized.zscore()*0.2+
        inb_winsorized.zscore()*0.1+
        num_winsorized.zscore()*0.03
    )

    # Build Filters representing the top and bottom baskets of stocks by our
    # combined ranking system. We'll use these as our tradeable universe each
    # day.
    #toma las mejores 600/2, que esten en el universo esas voy a comprar
    longs = combined_factor.top(TOTAL_POSITIONS//2, mask=universe)
     #toma las peores 600/2, que esten en el universo esas voy a vender
    shorts = combined_factor.bottom(TOTAL_POSITIONS//2, mask=universe)

    # The final output of our pipeline should only include
    # the top/bottom 300 stocks by our criteria
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
    #calcula los valores todos los dias con respecto a riesgo por sectores
    
    """
    Optional core function called automatically before the open of each market day.

    Parameters
    ----------
    context : AlgorithmContext
        See description above.
    data : BarData
        An object that provides methods to get price and volume data, check
        whether a security exists, and check the last time a security traded.
    """
    # Call algo.pipeline_output to get the output
    # Note: this is a dataframe where the index is the SIDs for all
    # securities to pass my screen and the columns are the factors
    # added to the pipeline object above
    context.pipeline_data = algo.pipeline_output('long_short_equity_template')

    # This dataframe will contain all of our risk loadings
    context.risk_loadings = algo.pipeline_output('risk_factors')


def record_vars(context, data):
    """
    A function scheduled to run every day at market close in order to record
    strategy information.

    Parameters
    ----------
    context : AlgorithmContext
        See description above.
    data : BarData
        See description above.
    """
    # Plot the number of positions over time.
    algo.record(num_positions=len(context.portfolio.positions))


# Called at the start of every month in order to rebalance
# the longs and shorts lists

#maximizar entabiidad
def rebalance(context, data):
    """
    A function scheduled to run once every Monday at 10AM ET in order to
    rebalance the longs and shorts lists.

    Parameters
    ----------
    context : AlgorithmContext
        See description above.
    data : BarData
        See description above.
    """
    # Retrieve pipeline output
    pipeline_data = context.pipeline_data

    risk_loadings = context.risk_loadings

    # Here we define our objective for the Optimize API. We have
    # selected MaximizeAlpha because we believe our combined factor
    # ranking to be proportional to expected returns. This routine
    # will optimize the expected return of our algorithm, going
    # long on the highest expected return and short on the lowest.
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

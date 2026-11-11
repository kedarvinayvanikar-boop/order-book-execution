-- Execution costs and fill rates. Each experiment is kept separate.
SELECT o.experiment_id, o.style, o.side,
       CASE WHEN o.quantity <= 100 THEN 'small'
            WHEN o.quantity <= 300 THEN 'medium' ELSE 'large' END AS size_bucket,
       COUNT(*) AS orders,
       AVG(1.0*x.filled_quantity/o.quantity) AS fill_rate, AVG(x.remaining_quantity=0) AS full_fill_probability,
       AVG(x.slippage_bps) AS slippage_bps,
       AVG(x.implementation_cost) AS implementation_cost,
       AVG(x.price_impact_percentage) AS impact_percentage
FROM orders o JOIN executions x USING (experiment_id,order_id)
GROUP BY o.experiment_id,o.style,o.side,size_bucket;

-- Queue placement and the cost of waiting.
SELECT o.experiment_id, o.quantity_ahead/100*100 AS queue_bucket,
       AVG(1.0*x.filled_quantity/o.quantity) AS fill_rate, AVG(x.remaining_quantity=0) AS full_fill_probability,
       AVG(x.events_to_fill) AS events_to_fill, AVG(x.adverse_selection_5) AS adverse_selection
FROM orders o JOIN executions x USING (experiment_id,order_id)
WHERE o.style='PASSIVE'
GROUP BY o.experiment_id,queue_bucket;

SELECT e.experiment_id,e.event_type,COUNT(*) AS observations,AVG(s.spread) AS average_spread
FROM events e JOIN book_states s USING(experiment_id,event_id)
GROUP BY e.experiment_id,e.event_type;

-- Missing future quotes are excluded from the direction denominator.
WITH forward AS (
 SELECT experiment_id,imbalance,midpoint,
        LEAD(midpoint) OVER (PARTITION BY experiment_id ORDER BY event_id) AS next_midpoint
 FROM book_states
)
SELECT experiment_id,CAST((imbalance+1)*2.5 AS INTEGER) AS imbalance_bucket,
       COUNT(*) AS observations,AVG(next_midpoint>midpoint) AS probability_up,
       AVG(next_midpoint-midpoint) AS average_move
FROM forward WHERE midpoint IS NOT NULL AND next_midpoint IS NOT NULL
GROUP BY experiment_id,imbalance_bucket;

SELECT o.experiment_id,o.order_id,o.side,o.style,x.implementation_cost
FROM orders o JOIN executions x USING(experiment_id,order_id)
WHERE x.implementation_cost IS NOT NULL
ORDER BY x.implementation_cost DESC LIMIT 20;

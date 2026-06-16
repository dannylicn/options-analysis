-- ============================================================
-- 期权数据采集系统 - PostgreSQL Schema
-- ============================================================
-- 
-- 设计原则:
--   1. 原始数据和汇总数据分离 (采集层 vs 分析层)
--   2. 为高频查询建索引 (按日期+标的查询是最常见的)
--   3. 预留扩展 (股价历史、事件标注、策略回测)
--   4. 数据类型精确 (NUMERIC 而非 FLOAT, 避免浮点误差)
--
-- 使用:
--   psql -U your_user -d your_db -f schema.sql
-- ============================================================


-- 清理 (首次建库时取消注释)
-- DROP SCHEMA IF EXISTS options CASCADE;

CREATE SCHEMA IF NOT EXISTS options;
SET search_path TO options, public;


-- ============================================================
-- 1. 标的股票主表
-- ============================================================
CREATE TABLE IF NOT EXISTS symbols (
    symbol          VARCHAR(10)     PRIMARY KEY,
    name            VARCHAR(200),
    sector          VARCHAR(50),
    market_cap      BIGINT,
    notes           TEXT,
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW()
);

COMMENT ON TABLE symbols IS '跟踪的标的股票列表';

INSERT INTO symbols (symbol, name, sector, notes) VALUES
    ('NIO',  'NIO Inc',                    'EV',       '蔚来 - 中国智能电动车'),
    ('TIGR', 'UP Fintech Holding',         'Fintech',  '老虎证券 - 跨境互联网券商'),
    ('TSLA', 'Tesla Inc',                  'EV',       '特斯拉'),
    ('FUTU', 'Futu Holdings',              'Fintech',  '富途证券'),
    ('BYDDY','BYD Company',                'EV',       '比亚迪')
ON CONFLICT (symbol) DO NOTHING;


-- ============================================================
-- 2. 股价历史 (每日)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    symbol          VARCHAR(10)     NOT NULL REFERENCES symbols(symbol),
    trade_date      DATE            NOT NULL,
    open            NUMERIC(12,4),
    high            NUMERIC(12,4),
    low             NUMERIC(12,4),
    close           NUMERIC(12,4)   NOT NULL,
    volume          BIGINT,
    vwap            NUMERIC(12,4),
    
    PRIMARY KEY (symbol, trade_date)
);

COMMENT ON TABLE stock_prices IS '标的股票每日价格, 用于和期权数据关联分析';

CREATE INDEX idx_stock_prices_date ON stock_prices (trade_date);


-- ============================================================
-- 3. 期权链快照 (核心表, 数据量最大)
-- ============================================================
CREATE TABLE IF NOT EXISTS options_snapshots (
    id              BIGSERIAL       PRIMARY KEY,
    collect_date    DATE            NOT NULL,
    symbol          VARCHAR(10)     NOT NULL REFERENCES symbols(symbol),
    contract_symbol VARCHAR(50)     NOT NULL,
    
    -- 合约属性
    expiry          DATE            NOT NULL,
    side            VARCHAR(4)      NOT NULL CHECK (side IN ('call', 'put')),
    strike          NUMERIC(10,2)   NOT NULL,
    
    -- 价格数据
    last_price      NUMERIC(10,4),
    bid             NUMERIC(10,4),
    ask             NUMERIC(10,4),
    
    -- 核心指标
    volume          INTEGER         DEFAULT 0,
    open_interest   INTEGER         DEFAULT 0,
    implied_volatility NUMERIC(8,6) DEFAULT 0,
    
    -- 元数据
    in_the_money    BOOLEAN         DEFAULT FALSE,
    days_to_expiry  INTEGER,
    
    -- 防重复
    UNIQUE (collect_date, contract_symbol)
);

COMMENT ON TABLE options_snapshots IS '每日期权链完整快照, 每个合约一行';
COMMENT ON COLUMN options_snapshots.implied_volatility IS '隐含波动率, 原始小数 (如 0.85 = 85%)';
COMMENT ON COLUMN options_snapshots.days_to_expiry IS '距到期日天数, 采集时自动计算';

-- 高频查询索引
CREATE INDEX idx_snap_date_symbol ON options_snapshots (collect_date, symbol);
CREATE INDEX idx_snap_symbol_expiry ON options_snapshots (symbol, expiry);
CREATE INDEX idx_snap_date_symbol_side ON options_snapshots (collect_date, symbol, side);
CREATE INDEX idx_snap_oi ON options_snapshots (open_interest DESC) WHERE open_interest > 0;
CREATE INDEX idx_snap_volume ON options_snapshots (volume DESC) WHERE volume > 0;


-- ============================================================
-- 4. 每日汇总表 (预计算, 加速分析查询)
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_summary (
    symbol          VARCHAR(10)     NOT NULL REFERENCES symbols(symbol),
    collect_date    DATE            NOT NULL,
    
    -- 股价
    stock_price     NUMERIC(10,4),
    stock_change_pct NUMERIC(8,4),
    
    -- OI 汇总
    total_call_oi   BIGINT          DEFAULT 0,
    total_put_oi    BIGINT          DEFAULT 0,
    oi_pc_ratio     NUMERIC(8,4),
    
    -- Volume 汇总
    total_call_volume BIGINT        DEFAULT 0,
    total_put_volume  BIGINT        DEFAULT 0,
    vol_pc_ratio    NUMERIC(8,4),
    
    -- IV 汇总 (OI 加权平均, 存为百分比)
    avg_call_iv     NUMERIC(8,2),
    avg_put_iv      NUMERIC(8,2),
    
    -- 关键行权价
    max_call_oi_strike NUMERIC(10,2),
    max_put_oi_strike  NUMERIC(10,2),
    max_pain        NUMERIC(10,2),
    
    -- 元数据
    total_contracts INTEGER         DEFAULT 0,
    total_expiries  INTEGER         DEFAULT 0,
    
    PRIMARY KEY (symbol, collect_date)
);

COMMENT ON TABLE daily_summary IS '每日汇总指标, 由采集脚本计算后写入';
COMMENT ON COLUMN daily_summary.oi_pc_ratio IS 'Put OI / Call OI, <0.7偏多, >1.0偏空';
COMMENT ON COLUMN daily_summary.avg_call_iv IS 'OI加权平均隐含波动率 (百分比, 如 85.00 = 85%)';

CREATE INDEX idx_summary_date ON daily_summary (collect_date);


-- ============================================================
-- 5. 按到期日的汇总 (看短期 vs 长期情绪差异)
-- ============================================================
CREATE TABLE IF NOT EXISTS expiry_summary (
    symbol          VARCHAR(10)     NOT NULL REFERENCES symbols(symbol),
    collect_date    DATE            NOT NULL,
    expiry          DATE            NOT NULL,
    
    call_oi         INTEGER         DEFAULT 0,
    put_oi          INTEGER         DEFAULT 0,
    oi_pc_ratio     NUMERIC(8,4),
    
    call_volume     INTEGER         DEFAULT 0,
    put_volume      INTEGER         DEFAULT 0,
    vol_pc_ratio    NUMERIC(8,4),
    
    avg_call_iv     NUMERIC(8,2),
    avg_put_iv      NUMERIC(8,2),
    
    days_to_expiry  INTEGER,
    
    PRIMARY KEY (symbol, collect_date, expiry)
);

COMMENT ON TABLE expiry_summary IS '按到期日分组的汇总, 区分短期和长期情绪';

CREATE INDEX idx_expiry_summary_date ON expiry_summary (collect_date, symbol);


-- ============================================================
-- 6. 异常活动记录 (OI/Volume 异常变化)
-- ============================================================
CREATE TABLE IF NOT EXISTS unusual_activity (
    id              BIGSERIAL       PRIMARY KEY,
    detect_date     DATE            NOT NULL,
    symbol          VARCHAR(10)     NOT NULL REFERENCES symbols(symbol),
    contract_symbol VARCHAR(50),
    
    -- 异常类型
    alert_type      VARCHAR(30)     NOT NULL,
    -- 可选值: 'oi_spike', 'volume_spike', 'iv_spike', 
    --         'pc_ratio_extreme', 'large_block'
    
    -- 异常详情
    side            VARCHAR(4),
    strike          NUMERIC(10,2),
    expiry          DATE,
    
    current_value   NUMERIC(12,4),
    previous_value  NUMERIC(12,4),
    change_pct      NUMERIC(8,2),
    
    -- 上下文
    description     TEXT,
    
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

COMMENT ON TABLE unusual_activity IS '自动检测的异常期权活动';

CREATE INDEX idx_unusual_date ON unusual_activity (detect_date, symbol);
CREATE INDEX idx_unusual_type ON unusual_activity (alert_type);


-- ============================================================
-- 7. 事件标注 (手动或自动标注重大事件)
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id              SERIAL          PRIMARY KEY,
    event_date      DATE            NOT NULL,
    symbol          VARCHAR(10)     REFERENCES symbols(symbol),
    
    event_type      VARCHAR(30)     NOT NULL,
    -- 可选值: 'earnings', 'regulatory', 'product_launch', 
    --         'macro', 'geopolitical', 'insider', 'other'
    
    title           VARCHAR(200)    NOT NULL,
    description     TEXT,
    impact          VARCHAR(10),
    -- 可选值: 'positive', 'negative', 'neutral', 'unknown'
    
    source_url      TEXT,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

COMMENT ON TABLE events IS '重大事件标注, 用于关联分析期权异常和事件的因果关系';

CREATE INDEX idx_events_date ON events (event_date);
CREATE INDEX idx_events_symbol ON events (symbol, event_date);

-- 预填一些已知事件
INSERT INTO events (event_date, symbol, event_type, title, impact) VALUES
    ('2026-05-22', 'TIGR', 'regulatory', '证监会处罚: 罚没4.112亿元', 'negative'),
    ('2026-05-22', 'FUTU', 'regulatory', '证监会处罚: 罚没18.5亿元', 'negative'),
    ('2026-05-21', 'NIO',  'earnings',   'NIO 2026 Q1 财报发布', 'positive'),
    ('2026-03-19', 'TIGR', 'earnings',   'TIGR 2025 Q4 财报发布', 'positive')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 8. 采集任务日志
-- ============================================================
CREATE TABLE IF NOT EXISTS collection_log (
    id              SERIAL          PRIMARY KEY,
    collect_date    DATE            NOT NULL,
    symbol          VARCHAR(10)     NOT NULL,
    status          VARCHAR(10)     NOT NULL DEFAULT 'success',
    -- 可选值: 'success', 'failed', 'partial'
    
    contracts_count INTEGER         DEFAULT 0,
    duration_secs   NUMERIC(8,2),
    error_message   TEXT,
    
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

COMMENT ON TABLE collection_log IS '采集任务执行日志, 监控数据完整性';

CREATE INDEX idx_log_date ON collection_log (collect_date);


-- ============================================================
-- 分析视图 (常用查询封装成 VIEW)
-- ============================================================

-- 视图 1: 每日情绪看板
CREATE OR REPLACE VIEW v_daily_sentiment AS
SELECT 
    ds.collect_date,
    ds.symbol,
    s.name,
    ds.stock_price,
    ds.stock_change_pct,
    ds.oi_pc_ratio,
    ds.vol_pc_ratio,
    ds.avg_call_iv,
    ds.avg_put_iv,
    ds.total_call_oi,
    ds.total_put_oi,
    ds.max_call_oi_strike,
    ds.max_put_oi_strike,
    ds.max_pain,
    -- 情绪标签
    CASE 
        WHEN ds.oi_pc_ratio < 0.5 THEN '极度看多'
        WHEN ds.oi_pc_ratio < 0.7 THEN '偏多'
        WHEN ds.oi_pc_ratio < 1.0 THEN '中性'
        WHEN ds.oi_pc_ratio < 1.5 THEN '偏空'
        ELSE '极度看空'
    END AS sentiment,
    -- 事件标注
    e.title AS event_title,
    e.impact AS event_impact
FROM daily_summary ds
JOIN symbols s ON ds.symbol = s.symbol
LEFT JOIN events e ON ds.symbol = e.symbol AND ds.collect_date = e.event_date
ORDER BY ds.collect_date DESC, ds.symbol;

COMMENT ON VIEW v_daily_sentiment IS '每日情绪看板: P/C Ratio + 情绪标签 + 关联事件';


-- 视图 2: OI 变化趋势 (日对日变化)
CREATE OR REPLACE VIEW v_oi_changes AS
SELECT 
    curr.collect_date,
    curr.symbol,
    curr.stock_price,
    curr.total_call_oi,
    curr.total_put_oi,
    curr.oi_pc_ratio,
    -- 日对日变化
    curr.total_call_oi - prev.total_call_oi AS call_oi_change,
    curr.total_put_oi - prev.total_put_oi AS put_oi_change,
    curr.oi_pc_ratio - prev.oi_pc_ratio AS pc_ratio_change,
    -- 变化百分比
    CASE WHEN prev.total_call_oi > 0 
        THEN ROUND((curr.total_call_oi - prev.total_call_oi)::NUMERIC / prev.total_call_oi * 100, 2)
        ELSE NULL 
    END AS call_oi_change_pct,
    CASE WHEN prev.total_put_oi > 0 
        THEN ROUND((curr.total_put_oi - prev.total_put_oi)::NUMERIC / prev.total_put_oi * 100, 2)
        ELSE NULL 
    END AS put_oi_change_pct
FROM daily_summary curr
LEFT JOIN daily_summary prev 
    ON curr.symbol = prev.symbol 
    AND prev.collect_date = (
        SELECT MAX(collect_date) 
        FROM daily_summary 
        WHERE symbol = curr.symbol 
        AND collect_date < curr.collect_date
    )
ORDER BY curr.collect_date DESC, curr.symbol;

COMMENT ON VIEW v_oi_changes IS 'OI日对日变化量和变化率, 用于发现突变';


-- 视图 3: IV 历史趋势
CREATE OR REPLACE VIEW v_iv_trend AS
SELECT 
    collect_date,
    symbol,
    stock_price,
    avg_call_iv,
    avg_put_iv,
    avg_put_iv - avg_call_iv AS iv_skew,
    -- IV 的移动平均 (需要足够数据后才有意义)
    AVG(avg_call_iv) OVER (
        PARTITION BY symbol ORDER BY collect_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS call_iv_5d_ma,
    AVG(avg_put_iv) OVER (
        PARTITION BY symbol ORDER BY collect_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS put_iv_5d_ma
FROM daily_summary
ORDER BY collect_date DESC, symbol;

COMMENT ON VIEW v_iv_trend IS 'IV历史趋势, 含5日均线和put-call skew';


-- 视图 4: 最大 OI 合约 (每天每只股票的 top 10)
CREATE OR REPLACE VIEW v_top_oi_contracts AS
SELECT *
FROM (
    SELECT 
        os.collect_date,
        os.symbol,
        os.side,
        os.strike,
        os.expiry,
        os.open_interest,
        os.volume,
        ROUND(os.implied_volatility * 100, 2) AS iv_pct,
        os.last_price,
        ROW_NUMBER() OVER (
            PARTITION BY os.collect_date, os.symbol 
            ORDER BY os.open_interest DESC
        ) AS oi_rank
    FROM options_snapshots os
    WHERE os.open_interest > 0
) ranked
WHERE oi_rank <= 10;

COMMENT ON VIEW v_top_oi_contracts IS '每天每只股票OI最大的前10个合约';


-- ============================================================
-- 实用查询示例 (保存为注释, 供参考)
-- ============================================================

/*

-- 1. 查看 TIGR 处罚前后的情绪变化
SELECT * FROM v_daily_sentiment 
WHERE symbol = 'TIGR' 
AND collect_date BETWEEN '2026-05-15' AND '2026-05-30'
ORDER BY collect_date;

-- 2. 找 OI 突变的日子 (call 或 put OI 变化超过 50%)
SELECT * FROM v_oi_changes 
WHERE (call_oi_change_pct > 50 OR call_oi_change_pct < -50
    OR put_oi_change_pct > 50 OR put_oi_change_pct < -50)
AND symbol = 'TIGR'
ORDER BY collect_date;

-- 3. 查看 NIO 某天的完整期权链 (按 OI 排序)
SELECT side, strike, expiry, open_interest, volume, 
       ROUND(implied_volatility * 100, 2) AS iv_pct
FROM options_snapshots
WHERE symbol = 'NIO' AND collect_date = '2026-05-24'
ORDER BY open_interest DESC
LIMIT 20;

-- 4. 对比多只股票的 IV 水平
SELECT collect_date, symbol, avg_call_iv, avg_put_iv, iv_skew
FROM v_iv_trend
WHERE collect_date = (SELECT MAX(collect_date) FROM daily_summary)
ORDER BY avg_call_iv DESC;

-- 5. 查看某只股票在事件日前后的数据
SELECT ds.*, e.title AS event
FROM daily_summary ds
LEFT JOIN events e ON ds.symbol = e.symbol AND ds.collect_date = e.event_date
WHERE ds.symbol = 'TIGR'
AND ds.collect_date BETWEEN '2026-05-19' AND '2026-05-26'
ORDER BY ds.collect_date;

-- 6. 统计每周的平均 P/C Ratio (看周度趋势)
SELECT symbol,
       DATE_TRUNC('week', collect_date)::DATE AS week_start,
       ROUND(AVG(oi_pc_ratio), 3) AS avg_pc_ratio,
       ROUND(AVG(avg_call_iv), 1) AS avg_iv,
       ROUND(AVG(stock_price), 2) AS avg_price
FROM daily_summary
GROUP BY symbol, DATE_TRUNC('week', collect_date)
ORDER BY symbol, week_start DESC;

-- 7. 找异常高 IV 的合约 (IV > 150%)
SELECT collect_date, symbol, side, strike, expiry,
       ROUND(implied_volatility * 100, 2) AS iv_pct,
       open_interest, volume
FROM options_snapshots
WHERE implied_volatility > 1.5
AND open_interest > 100
ORDER BY implied_volatility DESC
LIMIT 20;

*/


-- ============================================================
-- 权限 (可选, 如果你有多个用户/角色)
-- ============================================================
-- GRANT USAGE ON SCHEMA options TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA options TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA options TO your_app_user;

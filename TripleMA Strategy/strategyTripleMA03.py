# encoding: UTF-8

""""
基于三均线的交易策略，适合用在RB88 5分钟线上。
策略逻辑：
1. 信号：MA10，MA20金叉死叉
2. 过滤：MA120；
        MA10，MA120多头、空头排列(对比其的MA5）
3. 出场：ATR跟随止损
"""

from __future__ import division
from vnpy.trader.app.ctaStrategy.ctaTemplate import CtaTemplate, BarGenerator, ArrayManager


########################################################################
class TripleMAStrategy03(CtaTemplate):
    """基于三均线的交易策略"""
    className = 'TripleMAStrategy'
    author = 'Y.Raul'

    # 策略参数
    # 三均线长度设置
    maWindow1 = 10
    maWindow2 = 20
    maWindow3 = 120
    maWindow4 = 5
    slMultiplier = 4  # 计算止损距离的乘数
    atrWindow = 30  # ATR窗口数
    initDays = 10  # 初始化数据所用的天数
    fixedSize = 1  # 每次交易的数量

    # 策略变量
    atrValue = 0  # ATR指标数值

    intraTradeHigh = 0  # 持仓期内的最高点
    intraTradeLow = 0  # 持仓期内的最低点
    longStop = 0  # 多头止损
    shortStop = 0  # 空头止损

    # ma次新值
    ma10 = 0
    ma20 = 0
    # ma最新值
    ma11 = 0
    ma21 = 0
    ma31 = 0

    longEntry = 0  # 多头开仓
    longExit = 0  # 多头平仓
    shortEntry = 0
    shortExit = 0

    orderList = []  # 保存委托代码的列表

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'maWindow1',
                 'maWindow2',
                 'maWindow3',
                 'maWindow4'
                 'initDays',
                 'fixedSize']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'ma10',
               'ma11',
               'ma20',
               'ma21']
    # 同步列表
    syncList = ['pos']

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(TripleMAStrategy03, self).__init__(ctaEngine, setting)

        self.bm = BarGenerator(self.onBar, 5, self.onFiveBar)
        # 由于maWindow3的长度是120，所以ArrayManager的size要增加至150
        self.am = ArrayManager(size=150)

    # ----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' % self.name)

        # 载入历史数据，并采用回放计算的方式初始化策略数值
        initData = self.loadBar(self.initDays)
        for bar in initData:
            self.onBar(bar)

        self.putEvent()

    # ----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' % self.name)
        self.putEvent()

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' % self.name)
        self.putEvent()

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.bm.updateTick(tick)

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bm.updateBar(bar)

    # ----------------------------------------------------------------------
    def onFiveBar(self, bar):
        """收到5分钟K线"""
        # 保存K线数据
        self.am.updateBar(bar)
        if not self.am.inited:
            return

            # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        self.cancelAll()

        import talib
        # 计算指标数值
        ma3Array = self.am.sma(self.maWindow3, True)
        self.ma30 = ma3Array[-2]
        self.ma31 = ma3Array[-1]
        ma3_ma5 = talib.SMA(ma3Array, self.maWindow4)[-1]
        # ma3_ma5 = ma3Array.rolling(window = self.maWindow4)[-1]

        ma1Array = self.am.sma(self.maWindow1, True)
        self.ma10 = ma1Array[-2]
        self.ma11 = ma1Array[-1]
        # ma1_ma5 = ma1Array.rolling(window = self.maWindow4)[-1]
        ma1_ma5 = talib.SMA(ma1Array, self.maWindow4)[-1]
        ma2Array = self.am.sma(self.maWindow2, True)
        self.ma20 = ma2Array[-2]
        self.ma21 = ma2Array[-1]

        self.atrValue = self.am.atr(self.atrWindow)
        # 判断是否要进行交易
        # 当前无仓位，发送OCO开仓委托
        if self.pos == 0:
            self.intraTradeHigh = bar.high
            self.intraTradeLow = bar.low
            # 开多, bar.close > MA120,MA10 > MA120,MA10 上穿MA20，MA10、MA120向上
            if bar.close > self.ma31 and self.ma11 > self.ma31 \
                    and self.ma10 < self.ma20 and self.ma11 > self.ma21\
                    and self.ma31 > ma3_ma5 and self.ma11 > ma1_ma5:
                self.longEntry = bar.close
                self.buy(self.longEntry, self.fixedSize, True)
            # 开空, bar.close < MA120,MA10 < MA120,MA10 下穿MA20, MA10,MA120向下
            elif bar.close < self.ma31 and self.ma11 < self.ma31 \
                    and self.ma10 > self.ma20 and self.ma11 < self.ma21\
                    and self.ma31 < ma3_ma5 and self.ma11 < ma1_ma5:
                self.shortEntry = bar.close
                self.short(self.shortEntry, self.fixedSize, True)
        else:
            # 跟随止损
            # 持有多头仓位
            if self.pos > 0:
                self.intraTradeHigh = max(self.intraTradeHigh, bar.high)
                self.intraTradeLow = bar.low
                self.longStop = self.intraTradeHigh - self.atrValue * self.slMultiplier
                if bar.close < self.longStop:
                    self.sell(bar.close, abs(self.pos), True)
            # 持有空头仓位
            if self.pos < 0:
                self.intraTradeHigh = bar.high
                self.intraTradeLow = min(self.intraTradeLow, bar.low)
                self.shortStop = self.intraTradeLow + self.atrValue * self.slMultiplier
                if bar.close > self.shortStop:
                    self.cover(bar.close, abs(self.pos), True)
        # 发出状态更新事件
        self.putEvent()

        # ----------------------------------------------------------------------

    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        pass

    # ----------------------------------------------------------------------
    def onTrade(self, trade):
        # 发出状态更新事件
        self.putEvent()

    # ----------------------------------------------------------------------
    def onStopOrder(self, so):
        """停止单推送"""
        pass
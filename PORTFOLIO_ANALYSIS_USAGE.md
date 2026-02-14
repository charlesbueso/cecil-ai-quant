# Portfolio Analysis with Cecil AI

## Analyzing Your Fidelity Account

You can now analyze your portfolio by passing multiple CSV files to Cecil AI.

### Example Commands

#### Basic Portfolio Analysis
```bash
python -m cecil.main "Analyze my portfolio and tell me how it's performing" \
  --file assets/fidelity-february/Portfolio_Positions_Feb-14-2026.csv \
  --file assets/fidelity-february/History_for_Account_Z23193615.csv
```

#### Trade Recommendations for Next 2 Weeks
```bash
python -m cecil.main "Based on my current portfolio positions and trading history, what trades should I execute in the next two weeks? Provide specific buy/sell recommendations with position sizes and rationale." \
  --file assets/fidelity-february/Portfolio_Positions_Feb-14-2026.csv \
  --file assets/fidelity-february/History_for_Account_Z23193615.csv \
  --max-iterations 15
```

#### Risk Assessment
```bash
python -m cecil.main "Assess the risk level of my current portfolio and suggest rebalancing strategies" \
  --file assets/fidelity-february/Portfolio_Positions_Feb-14-2026.csv \
  --file assets/fidelity-february/History_for_Account_Z23193615.csv \
  --html
```

#### Performance Analysis
```bash
python -m cecil.main "Analyze my trading history and identify which trades were winners vs losers. What patterns do you see in my trading behavior?" \
  --file assets/fidelity-february/History_for_Account_Z23193615.csv \
  --file assets/fidelity-february/Portfolio_Positions_Feb-14-2026.csv
```

#### Tax Loss Harvesting
```bash
python -m cecil.main "Identify positions in my portfolio that could benefit from tax loss harvesting and recommend specific actions" \
  --file assets/fidelity-february/Portfolio_Positions_Feb-14-2026.csv \
  --file assets/fidelity-february/History_for_Account_Z23193615.csv
```

### What the Agents Will Do

When you provide these files, Cecil's agents will:

1. **Portfolio Analyst**
   - Review your current positions (GOOGL, QUBT, FVRR, etc.)
   - Calculate total gains/losses
   - Assess concentration risk (GOOGL at 57%, QUBT at 41%)
   - Evaluate each position's performance

2. **Quant Researcher**
   - Pull current market data for your holdings
   - Calculate technical indicators
   - Analyze momentum and trends
   - Compare against benchmarks

3. **Research Intelligence**
   - Gather recent news on your holdings
   - Check market sentiment
   - Review macroeconomic factors

4. **Project Manager**
   - Synthesize all analyses
   - Provide actionable recommendations
   - Suggest specific trades with sizing

### Sample Output

You can expect recommendations like:

```
ACTIONABLE RECOMMENDATIONS FOR NEXT 2 WEEKS:

SELL/TRIM:
1. GOOGL - Reduce position by 20% ($1,161)
   - Currently 57.76% of portfolio (overconcentrated)
   - Take profits at +164.56% gain
   - Target: Reduce to 40% of portfolio

2. BRAXF - Close position (worthless)
   - Currently -100% total loss
   - Remove dead weight

BUY/ADD:
1. Diversify into defensive sectors
   - Consider: Consumer staples ETF (VDC) - $1,500
   - Healthcare ETF (VHT) - $1,500
   - Rationale: Over-concentrated in tech/speculative

HOLD:
1. QUBT - Monitor closely
   - Up +39% but highly volatile
   - Set stop-loss at $7.00
   - Consider taking partial profits if hits $10

TIMELINE: Execute over 3 trading sessions to minimize impact
```

### Tips for Better Results

1. **Be Specific**: Ask for concrete actions with position sizes
2. **Use More Iterations**: Complex portfolio analysis benefits from 10-15 iterations
3. **Generate Reports**: Use `--html` or `--pdf` to save recommendations
4. **Update Monthly**: Re-run analysis as your portfolio evolves
5. **Compare Strategies**: Run the backtest comparison to see how AI picks vs quant strategies

### Windows Command Line

If you're on Windows (PowerShell or CMD), use:

```powershell
python -m cecil.main "Analyze my portfolio performance" --file assets/fidelity-february/Portfolio_Positions_Feb-14-2026.csv --file assets/fidelity-february/History_for_Account_Z23193615.csv
```

(No backslash for line continuation - put it all on one line)

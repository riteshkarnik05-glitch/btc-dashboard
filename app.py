        if eng["trade_dir"] != 0 and eng["tp1_reached"]:
            old_label = "LONG" if eng["trade_dir"] == 1 else "SHORT"
            if eng["trade_dir"] == 1:
                runner_pts = max(0.0, c - eng["entry_price"])
            else:
                runner_pts = max(0.0, eng["entry_price"] - c)
            runner_pnl_3q = runner_pts * RUNNER_QTY
            eng["gross_profit"] += runner_pnl_3q
            tot_flip_pnl = eng["booked_pnl_10q"] + runner_pnl_3q
            flip_status = "✅ 7Q TP1 + 3Q FLIP"
            flip_pnl_txt = "+" + fmt_pts(tot_flip_pnl)
            flip_row = {
                "time": bar_ist,
                "type": old_label + " (10Q)",
                "entry": eng["entry_price"],
                "exit": c,
                "status": flip_status,
                "pnl": flip_pnl_txt,
                "color": "#22c55e"
            }
            eng["history"].insert(0, flip_row)
            eng["history"] = eng["history"][:40]

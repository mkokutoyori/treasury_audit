import pandas as pd, glob, os
pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 50)
pd.set_option('display.max_colwidth', 80)
BASE=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
STR_COLS=['TRN_REF_NO','AC_NO','AC_CCY','USER_ID','AUTH_ID','AMOUNT_TAG','AC_NATURAL_GL','PRODUCT','AC_GL_DESC','MODULE','EXTERNAL_REF_NO','DESCRIPTION','DRCR_IND']
def rd(pattern):
    files=sorted(glob.glob(os.path.join(BASE,pattern)))
    dfs=[]
    for f in files:
        d=pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[''], encoding='utf-8-sig', low_memory=False)
        d['__src']=os.path.basename(f)
        dfs.append(d)
    df=pd.concat(dfs, ignore_index=True)
    for c in ['FCY_AMOUNT','LCY_AMOUNT']:
        if c in df.columns: df[c]=pd.to_numeric(df[c], errors='coerce')
    for c in ['TRN_DT']:
        if c in df.columns: df[c+'_d']=pd.to_datetime(df[c], errors='coerce')
    return df
def fx():   return rd('FX_TRANSACTIONS.csv')
def mm():   return rd('money_market_transactions.csv')
def clp():  return rd('calypso_transactions_*.csv')
def key():  return rd('transaction_history_of_key_account_*.csv')
def ctr():
    d=pd.read_csv(os.path.join(BASE,'MM_CONTRACT.csv'), dtype=str, keep_default_na=False, na_values=[''])
    for c in ['AMOUNT','LCY_AMOUNT','MAIN_COMP_RATE','MAIN_COMP_AMOUNT']:
        d[c]=pd.to_numeric(d[c], errors='coerce')
    for c in ['BOOKING_DATE','VALUE_DATE','MATURITY_DATE','TRADE_DATE']:
        d[c+'_d']=pd.to_datetime(d[c], format='%d-%b-%y', errors='coerce')
    return d

def ckey(): return rd('calypson_key_account_*.csv')

def cr():
    d=pd.read_csv(os.path.join(BASE,'creance_rattaché.csv'), dtype=str, keep_default_na=False,
                  na_values=[''], encoding='cp1252', low_memory=False)
    for c in d.columns:
        if d[c].dtype==object or str(d[c].dtype).startswith('str'):
            d[c]=d[c].str.replace('\xa0',' ',regex=False).str.strip()
    for c in ['FCY_AMOUNT','LCY_AMOUNT']:
        d[c]=pd.to_numeric(d[c], errors='coerce')
    d['TRN_DT_d']=pd.to_datetime(d.TRN_DT, format='%d-%b-%y', errors='coerce')
    d['STMT_DT_d']=pd.to_datetime(d.STMT_DT, format='%d-%b-%y', errors='coerce')
    d['__src']='creance_rattaché.csv'
    return d

def fkey():
    d = rd('final_key_accounts_*.csv')
    for c in d.columns:
        if d[c].dtype == object or str(d[c].dtype).startswith('str'):
            d[c] = d[c].str.replace('\xa0', ' ', regex=False).str.strip()
    return d

"""Validate concrete witnesses for the proposed next ISA; no exhaustive sweep."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sim.machine import Config,Machine
import corpus

isa=('SWAP','ADD','NAND','XOR','SHR','MUL','SKZ','HALT')
cfg=Config(W=4,a=2,p=3,I=4); machine=Machine(cfg,isa)
programs={
    'gray': [('SWAP',1),('ADD',1),('SHR',0),('XOR',1),('HALT',0)],
    'mul': [('MUL',1),('HALT',0)],
    'square': [('MUL',0),('HALT',0)],
    'a_xor_b_xor7': [('XOR',1),('SWAP',1),('XOR',0),('NAND',0),('SHR',0),('XOR',1),('HALT',0)],
}
un,bi=corpus.tables(); witnesses={}
for name,ops in programs.items():
    words=[isa.index(op)*2+arg for op,arg in ops]+[14]*(8-len(ops))
    binary=name in bi
    table=machine.truth_table_binary(words) if binary else machine.truth_table_unary(words)
    assert list(table)==(bi if binary else un)[name],name
    costs=[]
    for x in range(16):
        for y in range(16) if binary else (0,):
            memory=[0]*4
            if binary: memory[1]=y
            _,steps,end=machine.run(words,x,memory)
            assert end=='halt',name
            costs.append(steps)
    program=sum(word<<(k*4) for k,word in enumerate(words))
    witnesses[name]={'binary':binary,'program':f'0x{program:08x}',
                     'instructions':[f'{op} {arg}' for op,arg in ops],
                     'verified_inputs':len(costs),'all_inputs_halt':True,'max_steps':max(costs)}
result={'proposed_isa':list(isa),'W':4,'a':2,'p':3,'I':4,'opcode_bits':3,'operand_bits':1,
        'status':'proposal only; witnesses reference-verified; exhaustive coverage not measured',
        'rationale':'Retain SWAP/ADD/NAND/SKZ; add XOR, SHR, MUL and HALT to address corpus gaps. The HALT/SWAP/ADD/NAND/ROL combination and its binary mode were already swept.',
        'tradeoff':'One operand bit instead of two; only A and M[1] directly addressable. Compare named coverage and halting cost, not only operator count.',
        'witnesses':witnesses}
target=Path(__file__).resolve().parent/'next_isa_proposal.json'
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(witnesses,indent=2))

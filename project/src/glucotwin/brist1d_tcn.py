"""Small left-padded residual TCN for two endpoint deltas."""
import torch
from torch import nn
from torch.nn import functional as F


class CausalConv(nn.Module):
    def __init__(self,inputs,outputs,kernel,dilation):
        super().__init__()
        self.padding=(kernel-1)*dilation
        self.conv=nn.Conv1d(inputs,outputs,kernel,dilation=dilation)

    def forward(self,x): return self.conv(F.pad(x,(self.padding,0)))


class ResidualBlock(nn.Module):
    def __init__(self,inputs,outputs,kernel,dilation,dropout):
        super().__init__()
        self.body=nn.Sequential(CausalConv(inputs,outputs,kernel,dilation),nn.ReLU(),nn.Dropout(dropout),
                                CausalConv(outputs,outputs,kernel,dilation),nn.ReLU(),nn.Dropout(dropout))
        self.skip=nn.Identity() if inputs==outputs else nn.Conv1d(inputs,outputs,1)

    def forward(self,x): return F.relu(self.body(x)+self.skip(x))


class CompactTCN(nn.Module):
    def __init__(self,sequence_channels,context_features,architecture):
        super().__init__()
        blocks=[]; inputs=sequence_channels
        for dilation in architecture['dilations']:
            blocks.append(ResidualBlock(inputs,architecture['channels'],architecture['kernel_size'],dilation,architecture['dropout']))
            inputs=architecture['channels']
        self.sequence=nn.Sequential(*blocks)
        self.context=nn.Sequential(nn.Linear(context_features,architecture['context_hidden']),nn.ReLU(),nn.Dropout(architecture['dropout']))
        self.head=nn.Sequential(nn.Linear(inputs+architecture['context_hidden'],architecture['head_hidden']),nn.ReLU(),
                                nn.Linear(architecture['head_hidden'],architecture['outputs']))
        # Start as persistence; learn endpoint deltas from available labels.
        nn.init.zeros_(self.head[-1].weight); nn.init.zeros_(self.head[-1].bias)

    def forward(self,sequence,context):
        return self.head(torch.cat([self.sequence(sequence)[:,:,-1],self.context(context)],dim=1))

import torch
import torch.nn as nn
import torch.nn.functional as F
from model.AnomalyTransformer import AnomalyTransformer

# Custom KL loss function
def my_kl_loss(p, q):
    res = p * (torch.log(p + 0.0001) - torch.log(q + 0.0001))
    return torch.mean(torch.sum(res, dim=-1), dim=1)

# Initialize original model
model = AnomalyTransformer(win_size=100, enc_in=51, c_out=51, e_layers=3)
model.load_state_dict(torch.load('ture256SWaT_checkpoint.pth', map_location=torch.device('cpu')))

# Define new model class with mean calculation
class ModifiedModel(nn.Module):
    def __init__(self, original_model):
        super(ModifiedModel, self).__init__()
        self.original_model = original_model
        self.win_size = 100  # You need to define this since it's used in your loss computation
        self.criterion = nn.MSELoss(reduction='none')  # Use 'reduction' instead of 'reduce'

    def forward(self, x):
        # Get the original model output
        output, series, prior, sigma = self.original_model(x)

        # Initialize variables
        loss = torch.mean(self.criterion(x, output), dim=-1)
        series_loss = 0.0
        prior_loss = 0.0

        # Compute series and prior losses
        for u in range(len(prior)):
                if u == 0:
                    series_loss = my_kl_loss(series[u], (
                            prior[u] / torch.unsqueeze(torch.sum(prior[u], dim=-1), dim=-1).repeat(1, 1, 1,
                                                                                                   self.win_size)).detach()) * 50
                    prior_loss = my_kl_loss(
                        (prior[u] / torch.unsqueeze(torch.sum(prior[u], dim=-1), dim=-1).repeat(1, 1, 1,
                                                                                                self.win_size)),
                        series[u].detach()) * 50
                else:
                    series_loss += my_kl_loss(series[u], (
                            prior[u] / torch.unsqueeze(torch.sum(prior[u], dim=-1), dim=-1).repeat(1, 1, 1,
                                                                                                   self.win_size)).detach()) * 50
                    prior_loss += my_kl_loss(
                        (prior[u] / torch.unsqueeze(torch.sum(prior[u], dim=-1), dim=-1).repeat(1, 1, 1,
                                                                                                self.win_size)),
                        series[u].detach()) * 50
            # Metric
        # Compute metric and final loss
        metric = torch.softmax((-series_loss - prior_loss), dim=-1)
        cri = metric * loss
        cri = cri.detach().cpu().numpy()
        attens_energy = cri.reshape(-1)  # Reshape as needed

        return attens_energy

# Create modified model instance
modified_model = ModifiedModel(model)

# Save the modified model
# torch.save(modified_model.state_dict(), 'modified_model.pth')
# torch.save(modified_model, 'model_weights.pth')

# Load the modified model
new_model = ModifiedModel(model)  # Pass initialized model, not class
new_model.load_state_dict(torch.load('modified_model.pth', map_location=torch.device('cpu')))

# Test with dummy input
# output = new_model(torch.ones(256, 100, 51))  # Assuming input shape is correct
# print('new model output:')
# print(output)
# print('shape of output:', output.shape)
# print('length of output:', len(output))
# print('shape of begin output:', output[0].shape) 
# print('shape of end output:', output[-1].shape)   

# from torch.export import export
# from executorch.exir import to_edge

# # 1. torch.export: Defines the program with the ATen operator set.
# aten_dialect = export(new_model, (torch.ones(1, 100, 51),))

# # 2. to_edge: Make optimizations for Edge devices
# edge_program = to_edge(aten_dialect)

# # 3. to_executorch: Convert the graph to an ExecuTorch program
# executorch_program = edge_program.to_executorch()

# # 4. Save the compiled .pte program
# with open("more.pte", "wb") as file:
#     file.write(executorch_program.buffer)


import torchao
import copy


from torchao.quantization.GPTQ import Int4WeightOnlyGPTQQuantizer
from torchao.quantization import quantize_,int8_dynamic_activation_int8_weight, int4_weight_only
from torchao.quantization.quant_api import Int8DynActInt4WeightQuantizer
from torchao.quantization import int8_dynamic_activation_int4_weight,int8_dynamic_activation_int8_semi_sparse_weight
from torchao.quantization import quantize_, int4_weight_only
precision = torch.float32
group_size = 128

# you can enable [hqq](https://ithub.com/mobiusml/hqq/tree/master) quantization which is expected to improves accuracy through
# use_hqq flag for `int4_weight_only` quantization
# use_hqq = False
# quantize_(new_model, int4_weight_only(group_size=group_size, use_hqq=use_hqq))
## 会出错ValueError: Expected Tensor argument scales to have dtype torch.bfloat16, but got torch.float32 instead.



from torchao.quantization import quantize_, int8_weight_only
quantize_(new_model, int8_weight_only())
# 可行


# from torchao.quantization import quantize_, int8_dynamic_activation_int8_weight
# quantize_(new_model, int8_dynamic_activation_int8_weight())
# 可行


# from torchao.quantization import int8_dynamic_activation_int4_weight
# quantize_(new_model, int8_dynamic_activation_int4_weight())
## 可行


# from torchao.quantization import int8_dynamic_activation_int8_semi_sparse_weight
# quantize_(new_model, int8_dynamic_activation_int8_semi_sparse_weight())
# 会出错


# from torchao.quantization import quantize_, float8_dynamic_activation_float8_weight
# from torchao.quantization.observer import PerTensor
# quantize_(new_model, float8_dynamic_activation_float8_weight(granularity=PerTensor()))
## 会出错


# from torchao.quantization import quantize_, fpx_weight_only
# quantize_(new_model, fpx_weight_only(3, 2))
## 会出错






from torchao.utils import unwrap_tensor_subclass
m_unwrapped = unwrap_tensor_subclass(new_model)


sample_inputs = (torch.randn(1, 100, 51, dtype=precision), )


from torch._export import capture_pre_autograd_graph
from torch.export import export, ExportedProgram
from executorch.exir import EdgeProgramManager, ExecutorchProgramManager, to_edge
# default way
exported_program: ExportedProgram = export(m_unwrapped, sample_inputs)
edge: EdgeProgramManager = to_edge(exported_program)
executorch_program = edge.to_executorch()

with open("int8_dynamic_activation_int4_weight.pte", "wb") as file:
    file.write(executorch_program.buffer)


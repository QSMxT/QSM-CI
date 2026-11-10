function [output] = objective1(x,t,chi_plus, chi_minus, R_star_2_0, B0)
%Objective1 Summary of this function goes here
%   Detailed explanation goes here
C_plus  = x(1);
C_minus = x(2);
C_0     = x(3);
output = signalModel(t,C_plus, C_minus, C_0, chi_plus, chi_minus, R_star_2_0, B0);

end


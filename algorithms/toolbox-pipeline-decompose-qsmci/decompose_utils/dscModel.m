function [output] = dscModel(t, C_plus, C_minus, C_0, chi_plus, chi_minus, R_star_2_0, B0)
%S Summary of this function goes here
%   Detailed explanation goes here                
gamma = 42.58 * 2*pi;
a = (2*pi*gamma*B0)/(9*sqrt(3));

term2  = C_minus * exp(-(-a*chi_minus+R_star_2_0+(1j*(2/3)*-chi_minus*gamma*B0))*t);
term3  = (C_0 + C_plus)     * exp(-R_star_2_0*t);
output = term2 + term3;
end


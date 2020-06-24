r"""
VQE simulations in different sectors of the spin quantum number
===============================================================

.. meta::
    :property="og:description": Find the lowest-energy states of a Hamiltonian in different
        sector of the spin quantum number using the variational quantum eigensolver
        algorithm in PennyLane.
    :property="og:image": https://pennylane.ai/qml/_images/pes_h2.png

Quantum computers offer a promising avenue to perform first-principles simulations of the
electronic structure of molecules and materials that are currently intractable using classical
high-performance computers. In particular, the Variational Quantum Eigensolver (VQE) algorithm
:ref:`[1, 2]<vqe_references>` has proven to be a valuable quantum-classical computational
approach to find the lowest-energy eigenstate of the electronic Hamiltonian by using Noisy
Intermediate-Scale Quantum (NISQ) devices. (WILL ADD SOME REFERENCES HERE)

In the absence of `spin-orbit coupling <https://en.wikipedia.org/wiki/Spin-orbit_interaction>`_ the
electronic Hamiltonian matrix is block diagonal in the total spin quantum numbers. In other words,
one can expand the many-electron wave function of the molecule as a linear
combination of `Slater determinants <https://en.wikipedia.org/wiki/Slater_determinant>`_
with the same total-spin projection :math:`S_z`, and diagonalize the Hamiltonian in this basis
to obtain the energy spectrum in this particular subspace. For example, the figure below
shows the energy spectra of the Hydrogen molecule calculated in different spin sectors. Notice,
that the ground state with energy :math:`E_\mathrm{gs}=-1.136189` Ha has spin quantum numbers
:math:`S=0`, :math:`S_z=0` while the lowest-lying excited states, with energy
:math:`E^*=-0.478453` Ha, show a three-fold spin degeneracy with quantum numbers
:math:`S=1` and :math:`S_z=0, \pm 1`.

|

.. figure:: /demonstrations/vqe_uccsd/energy_spectra_h2_sto3g.png
    :width: 50%
    :align: center

|

Similarly, in the framework of VQE, if the quantum computer can be programmed to prepare many-body
states in a specific sector of the total-spin projection :math:`S_z`, the variational optimization
algorithm will allow us to estimate the energy of the lowest-lying state in this spin sector.
More specifically, if we run a VQE simulation for the :math:`\mathrm{H}_2` molecule in the
subspace of states with :math:`S_z=0` we will find the ground-state energy of the molecule. On the
other hand, if the VQE simulation is carried out in the subspace with :math:`S_z=1` the
optimized state will be in practice an excited state of the molecule as it is shown in the Figure 
above.

In this tutorial we will demonstrate how different functionalities implemented in PennyLane-QChem
can be put together to run VQE simulations in different sectors of the spin quantum numbers
to estimate the energies of the ground and the lowest-lying excited states of the hydrogen
molecule.

Let's get started! ⚛️

Building the Hamiltonian and the total spin observable :math:`\hat{S}^2`
------------------------------------------------------------------------

The first step is to import the required libraries and packages:
"""

import pennylane as qml
from pennylane import numpy as np
from pennylane import qchem
from pennylane.templates.subroutines import UCCSD

##################################################################################
# The second step is to specify the molecule whose properties we aim to calculate.
# This is done by providing the name, geometry and charge of the molecule.

name = 'h2'

##################################################################################
# The geometry of the molecule can be given in any format recognized by Open Babel.
# Here, we used a locally saved file in
# `xyz format <https://en.wikipedia.org/wiki/XYZ_file_format>`_ specifying the
# three-dimensional coordinates and symbols of the atomic species.

geometry = 'h2.xyz'

##############################################################################
# The charge determines the number of electrons that have been added or removed compared to the
# neutral molecule. In this example, we will consider a neutral molecule:

charge = 0

##############################################################################
# Now, we need to define two input parameters required to compute the mean field
# electronic structure of the molecule. First, the
# `multiplicity <https://en.wikipedia.org/wiki/Multiplicity_(chemistry)>`_ of the 
# `Hartree-Fock (HF) state <https://en.wikipedia.org/wiki/Hartree-Fock_method>`_, and
# the second one is the `atomic basis set <https://en.wikipedia.org/wiki/Basis_set_(chemistry)>`_
# used to represent the HF molecular orbitals. In this example, we will use the minimal
# basis STO-3g.

multiplicity = 1
basis_set = 'sto-3g'

##############################################################################
# PennyLane-QChem allows to define an `active space
# <https://en.wikipedia.org/wiki/Complete_active_space>`_ to expand the second-quantized
# Hamiltonian or any other observable relevant to compute different molecular properties.
# The active space is built by specifying the number of active electrons and active orbitals.
# For the hydrogen molecule described with a minimal basis set we will include all HF orbitals
# in our basis of single-particle states.

n_electrons = 2
n_orbitals = 2

##############################################################################
# Finally, to build the electronic Hamiltonian we have to define fermionic-to-qubit
# mapping, which can be either Jordan-Wigner (``jordan_wigner``) or Bravyi-Kitaev
# (``bravyi_kitaev``). The outputs of the function :func:`~.generate_hamiltonian` are
# the qubit Hamiltonian of the molecule and the number of qubits needed to represent it:

h, n_qubits = qml.qchem.generate_hamiltonian(
    name,
    geometry,
    charge,
    multiplicity,
    basis_set,
    n_active_electrons=n_electrons,
    n_active_orbitals=n_orbitals,
    mapping='jordan_wigner'
)

print('Number of qubits = ', n_qubits)
print('Hamiltonian is ', h)

##############################################################################
# That's it! From here on, we can use PennyLane as usual, employing its entire stack of
# algorithms and optimizers.
#
# Implementing the VQE algorithm
# ------------------------------
#
# PennyLane contains the :class:`~.VQECost` class, specifically
# built to implement the VQE algorithm. We begin by defining the device, in this case a simple
# qubit simulator:

dev = qml.device('default.qubit', wires=nr_qubits)

##############################################################################
# In VQE, the goal is to train a quantum circuit to prepare the ground state of the input
# Hamiltonian. This requires a clever choice of circuit, which should be complex enough to
# prepare the ground state, but also sufficiently easy to optimize. In this example, we employ a
# variational circuit that is capable of preparing the normalized states of the form
# :math:`\alpha|1100\rangle + \beta|0011\rangle` which encode the ground state wave function of
# the hydrogen molecule described with a minimal basis set. The circuit consists of single-qubit
# rotations on all wires, followed by three entangling CNOT gates, as shown in the figure below:
#
# |
#
# .. figure:: /demonstrations/variational_quantum_eigensolver/sketch_circuit.png
#     :width: 50%
#     :align: center
#
# |
#

##############################################################################
# In the circuit, we apply single-qubit rotations, followed by CNOT gates:


def circuit(params, wires):
    qml.BasisState(np.array([1, 1, 0, 0]), wires=wires)
    for i in wires:
        qml.Rot(*params[i], wires=i)
    qml.CNOT(wires=[2, 3])
    qml.CNOT(wires=[2, 0])
    qml.CNOT(wires=[3, 1])

##############################################################################
# .. note::
#
#     The qubit register has been initialized to :math:`|1100\rangle` which encodes the
#     Hartree-Fock state of the hydrogen molecule described with a `minimal basis
#     <https://en.wikipedia.org/wiki/Basis_set_(chemistry)#Minimal_basis_sets>`__.
#
# The cost function for optimizing the circuit can be created using the :class:`~.VQECost`
# class, which is tailored for VQE optimization. It requires specifying the
# circuit, target Hamiltonian, and the device, and returns a cost function that can
# be evaluated with the circuit parameters:


cost_fn = qml.VQECost(circuit, h, dev)


##############################################################################
# Wrapping up, we fix an optimizer and randomly initialize circuit parameters. For reliable
# results, we fix the seed of the random number generator, since in practice it may be necessary
# to re-initialize the circuit several times before convergence occurs.

opt = qml.GradientDescentOptimizer(stepsize=0.4)
np.random.seed(0)
params = np.random.normal(0, np.pi, (nr_qubits, 3))

print(params)

##############################################################################
# We carry out the optimization over a maximum of 200 steps, aiming to reach a convergence
# tolerance (difference in cost function for subsequent optimization steps) of :math:`\sim 10^{
# -6}`.

max_iterations = 200
max_iterations = 1
conv_tol = 1e-06

prev_energy = cost_fn(params)
for n in range(max_iterations):
    params = opt.step(cost_fn, params)
    energy = cost_fn(params)
    conv = np.abs(energy - prev_energy)

    if n % 20 == 0:
        print('Iteration = {:},  Ground-state energy = {:.8f} Ha,  Convergence parameter = {'
              ':.8f} Ha'.format(n, energy, conv))

    if conv <= conv_tol:
        break

    prev_energy = energy

print()
print('Final convergence parameter = {:.8f} Ha'.format(conv))
print('Final value of the ground-state energy = {:.8f} Ha'.format(energy))
print('Accuracy with respect to the FCI energy: {:.8f} Ha ({:.8f} kcal/mol)'.
        format(np.abs(energy - (-1.136189454088)), np.abs(energy - (-1.136189454088))*627.503))
print()
print('Final circuit parameters = \n', params)

##############################################################################
# Success! 🎉🎉🎉 The ground-state energy of the hydrogen molecule has been estimated with chemical
# accuracy (< 1 kcal/mol) with respect to the exact value of -1.136189454088 Hartree (Ha) obtained
# from a full configuration-interaction (FCI) calculation. This is because, for the optimized
# values of the single-qubit rotation angles, the state prepared by the VQE ansatz is precisely
# the FCI ground-state of the :math:`H_2` molecule :math:`|H_2\rangle_{gs} = 0.99 |1100\rangle - 0.10
# |0011\rangle`.
#
# What other molecules would you like to study using PennyLane?
#
# .. _vqe_references:
#
# References
# ----------
#
# 1. Alberto Peruzzo, Jarrod McClean *et al.*, "A variational eigenvalue solver on a photonic
#    quantum processor". `Nature Communications 5, 4213 (2014).
#    <https://www.nature.com/articles/ncomms5213?origin=ppub>`__
#
# 2. Yudong Cao, Jonathan Romero, *et al.*, "Quantum Chemistry in the Age of Quantum Computing".
#    `Chem. Rev. 2019, 119, 19, 10856-10915.
#    <https://pubs.acs.org/doi/10.1021/acs.chemrev.8b00803>`__
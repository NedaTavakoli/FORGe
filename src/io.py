#! /usr/bin/env python2.7

from util import *
import variant

'''
I/O support functions
'''

def read_genome(filename, target_chrom=None):
    G = dict()
    seq = None
    skip = False

    with open(filename, 'r') as f:
        for line in f:
            # Skip header line
            if line[0] == '>':
                if not skip and seq:
                    G[chrom] = seq
                chrom = line.rstrip().split(' ')[0][1:]
                seq = ''
                if target_chrom and not chrom == target_chrom:
                    skip = True
                else:
                    skip = False
                continue

            if not skip:
                seq += line.rstrip()
    if not skip and seq:
        G[chrom] = seq

    return G


def parse_1ksnp(filename, G=None):
    '''
        filename: Path to 1ksnp file containing variant information
        G: Genome sequence. If present, count variants inconsistent with G

        Return list of variants
    '''

    # Variant list
    v = []

    curr_var = None

    # Count of variants that are not consistent with G
    if G:
        wrong_count = 0

    with open(filename, 'r') as f:
        for line in f:
            row = line.rstrip().split('\t')

            if not curr_var:
                curr_var = variant.Variant(row[7], row[0], int(row[1])-1, row[2], [row[3]], [float(row[4])])
            else:
                if not row[7] == curr_var.name:
                    print("Error! Couldn't find all alternate alleles for variant %s" % curr_var.name)
                    exit()
                curr_var.add_alt(row[3], float(row[4]))

            if G and not G[curr_var.chrom][curr_var.pos:curr_var.pos+len(curr_var.orig)] == curr_var.orig:
                wrong_count += 1

            if curr_var.num_alts == int(row[6]):
                v.append(curr_var)
                curr_var = None

        if curr_var:
            v.append(curr_var)

    if G and wrong_count > 0:
        print('%d / %d variants are inconsistent with the reference genome!' % (wrong_count, len(S)))
        exit()

    return v

def write_vars(variants, locs, outfile):
    f_out = open(outfile, 'w')

    last_loc = None
    unique_count = 0

    curr_id = 0
    num_alts = 0
    count_added = 0
    num_target = len(locs)
    with open(variants, 'r') as f:
        for line in f:
            row = line.rstrip().split('\t')
            loc = int(row[1])

            while curr_id < num_target and loc > locs[curr_id]:
                curr_id += 1
                num_alts = 0

            if curr_id == num_target:
                break

            if loc == locs[curr_id]:
                # Convert location from 1-indexed to 0-indexed
                f_out.write(row[7] + '.' + str(num_alts) + '\tsingle\t' + row[0] + '\t' + str(loc-1) + '\t' + row[3] + '\n')
                if not loc == last_loc:
                    unique_count += 1
                last_loc = loc
                num_alts += 1

    f_out.close()
    print('Found %d / %d target vars' % (unique_count, num_target))

class HaplotypeParser:

    def __init__(self, filename):
        self.filename = filename
        self.indiv_chunk_end = 0
        self.indiv_chunk_size = 100000

    def get_freqs(self, var_ids, counts):
        '''
            Return an array containing the add-1 smoothed frequency for each combination of alleles among the SNPs given
        '''

        if (not self.indiv_chunk_end) or (var_ids[-1] >= self.indiv_chunk_end):
            self.read_next_chunk(var_ids[0], var_ids[-1])

        if var_ids[0] < self.indiv_chunk_start:
            print('Error! Variant id earlier than contained in the current chunk')

        num_vecs = 1
        for c in counts:
            num_vecs *= (c+1)

        total = num_vecs
        numH = len(self.haplotypes[0])
        good_turing = False
        if len(var_ids) > 8:
            # Good Turing smoothing
            good_turing = True
            allele_counts = [0] * num_vecs
        elif len(var_ids) > 1:
            # Plus 1 smoothing
            total = num_vecs + numH
            allele_counts = [1] * num_vecs
        else:
            # No smoothing
            total = numH
            allele_counts = [0] * num_vecs

        for i in range(numH):
            v = [self.haplotypes[j-self.indiv_chunk_start][i] for j in var_ids]
            allele_counts[self.vec_to_id(v, counts)] += 1

        if good_turing:
            freqs = [0] * (max(allele_counts)+1)
            for c in allele_counts:
                freqs[c] += 1

            smoothed_probs = self.good_turing_smoothing(freqs)
            allele_counts = [smoothed_probs[a] for a in allele_counts]
        else:
            allele_counts = [float(a) / total for a in allele_counts]

        return allele_counts

    def read_next_chunk(self, min_snp, max_snp):
        '''
            min_snp, max_snp: Line ids in the file of the first and last SNPs in the current window
        '''

        if max_snp < self.indiv_chunk_end:
            print('No need to update chunk')
            return

        if self.indiv_chunk_end:
            new_start = min(self.indiv_chunk_end, min_snp)
            new_end = self.indiv_chunk_end + self.indiv_chunk_size
        else:
            new_start = 0
            new_end = self.indiv_chunk_size

        while max_snp >= new_end:
            new_end += self.indiv_chunk_size

        haplotypes = []
        with open(self.filename, 'r') as f:
            line_id = 0
            for line in f:
                if line_id < new_start:
                    line_id += 1
                    continue
                elif line_id >= new_end:
                    break
                else:
                    haplotypes.append([int(allele) for allele in line.rstrip().split(',')])

        self.indiv_chunk_start = new_start
        self.indiv_chunk_end = new_end
        self.haplotypes = haplotypes

    def reset_chunk(self):
        self.indiv_chunk_start = None
        self.indiv_chunk_end = None

    def good_turing_smoothing(self, counts):
        '''
            counts: a list of count frequencies, i.e. counts[i] is the number of haplotypes with frequency i
            return: a list p of probabilities such that p[i] is the new probability for haplotypes with frequency i
        '''

        max_c = len(counts)
        adj_counts = [0.0] * max_c
        total_weight = 0.0
        for i in range(max_c-1):
            # No haplotypes with this frequency, so no need to compute probability
            if counts[i] == 0:
                continue

            next_count = counts[i+1]
            if next_count == 0:
                for j in range(i+1, max_c):
                    if counts[j] > 0:
                        break
                if counts[j] > 0:
                    next_count = counts[i] + float(counts[j] - counts[i]) / (j - i)
                else:
                    # No haplotypes with greater frequency
                    next_count = counts[i]

            adj_counts[i] = (i+1) * float(next_count) / counts[i]
            total_weight += (i+1) * float(next_count)

        # Last frequency
        adj_counts[-1] = i
        total_weight += i * counts[-1]

        return [i / total_weight for i in adj_counts]

    def vec_to_id(self, v, counts):
        id = 0
        for i in range(len(v)):
            if v[i] > counts[i]:
                print('Error in allele vector! Vector is ' + str(v) + ' but counts are ' + str(counts))
                traceback.print_stack()
                exit()

            id = id * (counts[i]+1) + v[i]

        return id




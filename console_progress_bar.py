import sys

class Console_progress_bar:
	def __init__(self, total, bar_length=40, on_finish=None):
		self.total = total
		self.current = 0
		self.bar_length = bar_length
		self.on_finish = on_finish

	def step(self, amount = 1):
		self.current += amount
		progress = min(self.current / self.total, 1.0)

		filled_len = int(self.bar_length * progress)
		bar = '#' * filled_len + '-' * (self.bar_length - filled_len)

		sys.stdout.write(f'\r[{bar}] {progress * 100:6.2f}%')
		sys.stdout.flush()

		if self.current >= self.total:
			sys.stdout.write('\n')
			if self.on_finish:
				self.on_finish()

	def reset(self):
		self.current = 0
		sys.stdout.write('\r' + ' ' * (self.bar_length + 10) + '\r')
		sys.stdout.flush()

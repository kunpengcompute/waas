obj-m += prf.o

KERNAL_DIR=/lib/modules/$(shell uname -r)/build

all:
	make -C $(KERNAL_DIR) M=$(PWD) modules
clean:
	make -C $(KERNAL_DIR) M=$(PWD) clean
	